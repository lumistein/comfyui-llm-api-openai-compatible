import os
import re
import json
import urllib.request
import urllib.error
import io
import base64
from PIL import Image


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
            "User-Agent": "openai-python/1.59.0",
            "Accept": "application/json",
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
            },
            "optional": {
                "image": (
                    "IMAGE",
                    {
                        "tooltip": "Optional image input for Multi-modal / Vision models (e.g. gpt-4o, gemini, etc.)"
                    }
                ),
                "template_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Connect a string output (like LLM Prompt Template Manager) to dynamically override the prompt template."
                    }
                )
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
        image=None,
        template_override="",
    ) -> tuple[str]:
        if template_override and template_override.strip():
            template = template_override
            print(f"[LLM API Node] Using dynamically overridden prompt template.")
        else:
            template = _load_prompt_template(prompt_file)
        messages = _parse_chatml(template, prompt)

        # Process image if provided for multimodal requests
        if image is not None:
            # ComfyUI image format is [B, H, W, C] (typically float tensor 0.0-1.0)
            # We take the first image in the batch
            try:
                img_tensor = image[0]
                img_np = (img_tensor.cpu().numpy() * 255.0).astype('uint8')
                
                # Check channels (usually 3 for RGB, but could be 1 for grayscale or 4 for RGBA)
                if img_np.shape[-1] == 1:
                    pil_img = Image.fromarray(img_np.squeeze(-1), mode="L")
                elif img_np.shape[-1] == 4:
                    pil_img = Image.fromarray(img_np, mode="RGBA").convert("RGB")
                else:
                    pil_img = Image.fromarray(img_np, mode="RGB")
                
                # Encode to JPEG base64
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG")
                base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{base64_image}"
                
                # Inject image into the last user message
                user_msg_found = False
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        orig_content = msg["content"]
                        msg["content"] = [
                            {"type": "text", "text": orig_content},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                        user_msg_found = True
                        break
                
                # If no user message was found in the ChatML template, append one at the end
                if not user_msg_found:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ""},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                    })
                print(f"[LLM API Node] Encoded image successfully and attached to user message.")
            except Exception as e:
                print(f"[LLM API Node] Failed to process image: {str(e)}")

        print(f"[LLM API Node] Sending {len(messages)} message(s) to {base_url} | model={model}")
        for m in messages:
            # Handle structured content preview (list vs str)
            if isinstance(m["content"], list):
                txt_preview = ""
                for part in m["content"]:
                    if part["type"] == "text":
                        txt_preview = part["text"]
                        break
                preview = f"[Multimodal] {txt_preview[:80].replace(chr(10), '\\n')}"
            else:
                preview = m["content"][:80].replace("\n", "\\n")
            print(f"  [{m['role']}] {preview}{'...' if len(preview) > 80 else ''}")

        result = _call_api(base_url, model, api_key, messages, max_tokens, temperature)
        print(f"[LLM API Node] Response ({len(result)} chars): {result[:120].replace(chr(10),' ')}{'...' if len(result) > 120 else ''}")

        return (result,)


class LLMPromptManagerNode:
    """
    ComfyUI custom node — LLM Prompt Template Manager
    ===================================================
    Allows reading, creating, modifying, and deleting prompt template files (.txt)
    directly inside the `prompts/` subfolder from the ComfyUI interface.

    Outputs
    -------
    template_content : STRING
        The loaded or saved content of the prompt template file.
    prompt_file : STRING
        The filename of the managed prompt template.
    """

    CATEGORY = "LLM / API"
    FUNCTION = "manage"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("template_content", "prompt_file")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        # We reuse LLMApiNode's file scanner
        return {
            "required": {
                "action": (
                    ["Read/Select", "Save/Create", "Delete"],
                    {
                        "default": "Read/Select",
                        "tooltip": (
                            "Select the operation to perform:\n"
                            "  Read/Select: Reads the chosen file's content.\n"
                            "  Save/Create: Overwrites the selected file OR creates a new file using 'new_filename'.\n"
                            "  Delete: Deletes the chosen file."
                        ),
                    },
                ),
                "filename": (
                    LLMApiNode._txt_files(),
                    {
                        "tooltip": "The prompt template file to manage.",
                    },
                ),
                "new_filename": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Optional. Use to create a NEW template. (e.g. 'summary_bot' or 'summary_bot.txt')",
                    },
                ),
                "content": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "The text content used when saving or creating a template.",
                    },
                ),
            }
        }

    def manage(
        self,
        action: str,
        filename: str,
        new_filename: str,
        content: str,
    ) -> tuple[str, str]:
        # Ensure prompts directory exists
        if not os.path.exists(PROMPTS_DIR):
            os.makedirs(PROMPTS_DIR, exist_ok=True)

        target_file = filename
        result_content = ""

        if action == "Read/Select":
            # Just read the selected file
            path = os.path.join(PROMPTS_DIR, filename)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    result_content = f.read()
                print(f"[LLM API Node] Prompt template loaded: {filename}")
            else:
                result_content = ""
                print(f"[LLM API Node] Warning: File not found: {filename}")

        elif action == "Save/Create":
            # Decide on filename
            new_fn = new_filename.strip()
            if new_fn:
                # Add .txt extension if not present
                if not new_fn.lower().endswith(".txt"):
                    new_fn += ".txt"
                target_file = new_fn

            path = os.path.join(PROMPTS_DIR, target_file)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            result_content = content
            print(f"[LLM API Node] Prompt template saved: {target_file}")

        elif action == "Delete":
            path = os.path.join(PROMPTS_DIR, filename)
            if os.path.isfile(path):
                # Never delete the last fallback default file if it's the only one
                all_files = LLMApiNode._txt_files()
                if len(all_files) <= 1 and filename == "prompt_body.txt":
                    print(f"[LLM API Node] Cannot delete the only remaining default prompt file.")
                    result_content = ""
                    with open(path, "r", encoding="utf-8") as f:
                        result_content = f.read()
                else:
                    os.remove(path)
                    print(f"[LLM API Node] Prompt template deleted: {filename}")
                    
                    # Fallback file path for output
                    remaining = LLMApiNode._txt_files()
                    target_file = remaining[0]
                    fallback_path = os.path.join(PROMPTS_DIR, target_file)
                    if os.path.isfile(fallback_path):
                        with open(fallback_path, "r", encoding="utf-8") as f:
                            result_content = f.read()
            else:
                result_content = ""
                print(f"[LLM API Node] Warning: File not found for deletion: {filename}")

        return (result_content, target_file)


# ---------------------------------------------------------------------------
# Node registration (imported by __init__.py)
# ---------------------------------------------------------------------------

NODE_CLASS_MAPPINGS = {
    "LLMApiNode": LLMApiNode,
    "LLMPromptManagerNode": LLMPromptManagerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMApiNode": "☁️ Cloud LLM (OpenAI-compatible)",
    "LLMPromptManagerNode": "📝 LLM Prompt Template Manager",
}
