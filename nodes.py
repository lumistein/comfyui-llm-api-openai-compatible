import os
import re
import json
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLACEHOLDER = "{{prompt_here}}"
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(NODE_DIR, "prompts")


def _load_prompt_template(filename: str = "prompt_body.txt") -> str:
    """Load the ChatML prompt template from the prompts/ subfolder."""
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"[LLM API Node] Prompt template not found: {path}\n"
            "Please place your .txt template files inside the 'prompts/' subfolder."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_chatml(template: str, user_prompt: str) -> list[dict]:
    """
    Parse a ChatML-formatted string into an OpenAI messages list.

    The template must follow the ChatML format:
        <|im_start|>role
        content
        <|im_end|>

    The special token {{prompt_here}} inside any content block is replaced
    with *user_prompt* before parsing.
    """
    # Inject user prompt into placeholder
    filled = template.replace(PLACEHOLDER, user_prompt)

    messages = []
    # Split on <|im_start|>, skip empty leading segment
    parts = re.split(r"<\|im_start\|>", filled)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Remove trailing <|im_end|>
        part = re.sub(r"<\|im_end\|>.*", "", part, flags=re.DOTALL).strip()
        if not part:
            continue
        # First line = role, rest = content
        lines = part.split("\n", 1)
        role = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        messages.append({"role": role, "content": content})

    return messages


def _call_api(
    base_url: str,
    model: str,
    api_key: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> str:
    """Send a chat-completion request to an OpenAI-compatible endpoint."""

    # Normalise base URL — accept any of these three forms:
    #   1. https://api.openai.com                          → append /v1/chat/completions
    #   2. https://api.openai.com/v1                       → append /chat/completions
    #   3. https://api.cerebras.ai/v1/chat/completions     → use as-is
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        url = base_url
    elif base_url.endswith("/v1"):
        url = f"{base_url}/chat/completions"
    else:
        url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"[LLM API Node] HTTP {e.code} from {url}:\n{error_body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"[LLM API Node] Connection error to {url}: {e.reason}"
        ) from e

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(
            f"[LLM API Node] Unexpected response format: {body}"
        ) from e


# ---------------------------------------------------------------------------
# ComfyUI Node
# ---------------------------------------------------------------------------

class LLMApiNode:
    """
    ComfyUI custom node — OpenAI-compatible Cloud LLM
    ===================================================
    Reads a ChatML-formatted prompt template from ``prompt_body.txt`` located
    in the same folder as this node.  The ``{{prompt_here}}`` placeholder
    inside the template is replaced with the *prompt* widget value before the
    request is sent.

    Outputs
    -------
    text : STRING
        The assistant's reply, ready to connect to any node that accepts a
        STRING input (e.g. ``Text Concatenate``, ``Show Text``, etc.).
    """

    CATEGORY = "LLM / API"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_NODE = True

    # List .txt files found in the prompts/ subfolder so the user can pick one
    @classmethod
    def _txt_files(cls) -> list[str]:
        if not os.path.isdir(PROMPTS_DIR):
            return ["prompt_body.txt"]
        files = sorted(f for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt"))
        return files if files else ["prompt_body.txt"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_url": (
                    "STRING",
                    {
                        "default": "https://api.openai.com",
                        "multiline": False,
                        "tooltip": (
                            "Base URL — any of the three formats is accepted:\n"
                            "  https://api.openai.com                        (base only)\n"
                            "  https://api.openai.com/v1                     (with /v1)\n"
                            "  https://api.cerebras.ai/v1/chat/completions   (full URL)"
                        ),
                    },
                ),
                "model": (
                    "STRING",
                    {
                        "default": "gpt-4o-mini",
                        "multiline": False,
                        "tooltip": "Model ID as accepted by the API (e.g. gpt-4o, claude-3-5-sonnet-20241022).",
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "API key / secret token.  Leave blank for local servers that don't require auth.",
                    },
                ),
                "prompt_file": (
                    cls._txt_files(),
                    {
                        "tooltip": (
                            "ChatML-formatted template file inside the prompts/ subfolder.\n"
                            "Place {{prompt_here}} where the user prompt should be inserted."
                        ),
                    },
                ),
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "User input that replaces {{prompt_here}} in the template.",
                    },
                ),
                "max_tokens": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 1,
                        "max": 32768,
                        "step": 1,
                        "tooltip": "Maximum number of tokens in the response.",
                    },
                ),
                "temperature": (
                    "FLOAT",
                    {
                        "default": 0.7,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "Sampling temperature (0 = deterministic, 2 = very random).",
                    },
                ),
            }
        }

    def run(
        self,
        base_url: str,
        model: str,
        api_key: str,
        prompt_file: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str]:
        template = _load_prompt_template(prompt_file)
        messages = _parse_chatml(template, prompt)

        print(f"[LLM API Node] Sending {len(messages)} message(s) to {base_url} | model={model}")
        for m in messages:
            preview = m["content"][:80].replace("\n", "\\n")
            print(f"  [{m['role']}] {preview}{'...' if len(m['content']) > 80 else ''}")

        result = _call_api(base_url, model, api_key, messages, max_tokens, temperature)
        print(f"[LLM API Node] Response ({len(result)} chars): {result[:120].replace(chr(10),' ')}{'...' if len(result) > 120 else ''}")

        return (result,)


# ---------------------------------------------------------------------------
# Node registration (imported by __init__.py)
# ---------------------------------------------------------------------------

NODE_CLASS_MAPPINGS = {
    "LLMApiNode": LLMApiNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMApiNode": "☁️ Cloud LLM (OpenAI-compatible)",
}
