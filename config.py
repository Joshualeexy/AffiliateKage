import os
from dotenv import load_dotenv
load_dotenv()

# LLM Configuration (Universal: Ollama, OpenRouter, OpenAI, DeepSeek, Groq)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
OLLAMA_MODEL = LLM_MODEL  # Backwards compatibility

# Headless CMS / Admin REST API
API_URL = os.getenv("API_URL")
API_TOKEN = os.getenv("API_TOKEN")

# ComfyUI Image Generation
COMFY_URL = os.getenv("COMFY_URL")
COMFY_START_CMD = os.getenv("COMFY_START_CMD", "cd ~/comfyui/ComfyUI && source venv/bin/activate && python main.py")
COMFY_TIMEOUT = int(os.getenv("COMFY_TIMEOUT", "600"))
COMFY_STEPS = int(os.getenv("COMFY_STEPS", "25"))
COMFY_MAX_RETRIES = int(os.getenv("COMFY_MAX_RETRIES", "3"))

# Amazon Affiliate
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")

# Image Provider: comfyui | openai | stability | fallback
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "comfyui").lower()

_required = {
    "LLM_MODEL": LLM_MODEL,
    "API_URL": API_URL,
    "API_TOKEN": API_TOKEN,
}

if IMAGE_PROVIDER == "comfyui":
    _required["COMFY_URL"] = COMFY_URL

if LLM_PROVIDER in {"openai", "openrouter"}:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        _required["LLM_API_KEY"] = api_key

_missing = [name for name, value in _required.items() if not value]

if _missing:
    raise RuntimeError(
        "Missing required configuration values: " + ", ".join(_missing)
    )