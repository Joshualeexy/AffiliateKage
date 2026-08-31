import logging
import subprocess
import os
import json
import re
from typing import Any
import requests

try:
    import ollama
except Exception:
    ollama = None

logger = logging.getLogger(__name__)

# Known default OpenAI-compatible provider endpoints
PROVIDER_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}


class OllamaClient:
    """
    Universal LLM client for AffiliateKage.
    Seamlessly operates with:
      - Local Ollama (default, 100% free offline)
      - OpenRouter (Claude 3.5 Sonnet, Gemini 2.5 Pro, DeepSeek R1, GPT-4o)
      - OpenAI (GPT-4o, o3-mini)
      - DeepSeek, Groq, Together, vLLM, or any custom OpenAI-compatible endpoint
    """

    def __init__(self, model_name: str = None):
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.model = model_name or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")

        # Resolve base URL
        custom_base = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        if custom_base:
            self.base_url = custom_base.rstrip("/")
        else:
            self.base_url = PROVIDER_ENDPOINTS.get(self.provider, "http://127.0.0.1:11434/v1")

        # Resolve API key
        self.api_key = (
            os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        )

    def generate(self, prompt: str, format: str | None = None, options: dict | None = None, **kwargs) -> dict:
        """
        Generate text using the configured provider.
        Returns a dict with `{'response': text}` to maintain 100% contract compatibility.
        """
        # 1. Native local Ollama if selected and available
        if self.provider == "ollama" and not os.getenv("LLM_BASE_URL") and ollama is not None:
            params = dict(kwargs)
            if format is not None:
                params["format"] = format
            if options is not None:
                params["options"] = options
            try:
                return ollama.generate(model=self.model, prompt=prompt, **params)
            except Exception as e:
                logger.warning("Local ollama.generate call failed (%s); trying OpenAI-compatible endpoint fallback...", e)

        # 2. Universal OpenAI-compatible Chat Completions API
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # OpenRouter optional discovery headers
        if "openrouter.ai" in endpoint:
            headers["HTTP-Referer"] = "https://github.com/Joshualeexy/AffiliateKage"
            headers["X-Title"] = "AffiliateKage"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        # Some providers support strict json_object response format
        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"response": content}
        except requests.exceptions.HTTPError as e:
            # If json_object is rejected by a provider that doesn't support response_format, retry without it
            if format == "json" and resp.status_code in (400, 422):
                logger.info("Provider rejected response_format, retrying without response_format param...")
                payload.pop("response_format", None)
                retry_resp = requests.post(endpoint, json=payload, headers=headers, timeout=600)
                retry_resp.raise_for_status()
                data = retry_resp.json()
                content = data["choices"][0]["message"]["content"]
                return {"response": content}
            raise RuntimeError(f"LLM API request failed ({self.provider} at {endpoint}): {e}\nResponse: {resp.text}")
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with LLM API ({self.provider} at {endpoint}): {e}")

    def unload(self) -> None:
        """Unload model from local GPU memory if using local Ollama. No-op for cloud APIs."""
        if self.provider != "ollama":
            return

        try:
            if ollama is not None:
                ollama.generate(model=self.model, prompt="", keep_alive=0)
                logger.info("Requested Ollama to unload model via keep_alive=0")
                return
        except Exception:
            pass

        # Fallback: run `ollama stop <model_name>` via subprocess
        try:
            subprocess.run(["ollama", "stop", self.model], check=True, capture_output=True)
            logger.info("Called `ollama stop %s` successfully", self.model)
        except Exception:
            pass


def extract_json(text: str | dict) -> Any:
    """Extract and parse JSON safely from LLM responses, stripping code fences and outer prose."""
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        raise ValueError(f"Expected str or dict, got {type(text)}")
    clean = text.strip()

    # Strip markdown code fences if present
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean)
    if match:
        clean = match.group(1).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Fallback to finding outermost JSON brackets
        fallback_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', clean)
        if fallback_match:
            return json.loads(fallback_match.group(1))
        raise
