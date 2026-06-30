"""
comfyui-llm-api-openai-compatible
===================================
ComfyUI custom node — send prompts to any OpenAI-compatible LLM API
(OpenAI, Anthropic via proxy, local Ollama, LM Studio, etc.)
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
