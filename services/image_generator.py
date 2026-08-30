import os
import time
import requests
from pathlib import Path
from typing import Optional

class ImageGenerator:
    """Unified image generation router supporting:
    - 'comfyui' (Local GPU via ComfyUI SDXL)
    - 'openai' (DALL-E 3 cloud API)
    - 'stability' (Stability AI SDXL cloud API)
    - 'fallback' (High-res photo search fallback via DDGS)
    """

    def __init__(self, output_dir: str = "generated"):
        self.provider = os.getenv("IMAGE_PROVIDER", "comfyui").lower()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.comfy_client = None

        if self.provider == "comfyui":
            from services.comfy import ComfyClient
            self.comfy_client = ComfyClient(workflow_path="services/workflow.json")

    def generate(self, prompt: str) -> Optional[str]:
        """Generate an image using the configured provider."""
        print(f"[ImageGenerator] Provider: '{self.provider}' | Prompt: {prompt[:80]}...")

        # Strategy 1: Local ComfyUI (Default for local GPU users)
        if self.provider == "comfyui":
            if self.comfy_client:
                return self.comfy_client.generate(prompt)

        # Strategy 2: OpenAI DALL-E 3 Cloud API
        elif self.provider in {"openai", "dalle"}:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("IMAGE_PROVIDER is set to 'openai' but OPENAI_API_KEY is missing in .env")
            return self._generate_openai(prompt, api_key)

        # Strategy 3: Stability AI Cloud API
        elif self.provider in {"stability", "stabilityai"}:
            api_key = os.getenv("STABILITY_API_KEY")
            if not api_key:
                raise ValueError("IMAGE_PROVIDER is set to 'stability' but STABILITY_API_KEY is missing in .env")
            return self._generate_stability(prompt, api_key)

        # Strategy 4: Web Search Fallback (Zero GPU, Zero API key)
        elif self.provider in {"fallback", "none", "search"}:
            return self._fallback_search(prompt)

        # Unknown provider fallback
        print(f"[ImageGenerator] Unknown provider '{self.provider}'. Falling back to local ComfyUI...")
        from services.comfy import ComfyClient
        return ComfyClient(workflow_path="services/workflow.json").generate(prompt)

    def _generate_openai(self, prompt: str, api_key: str) -> str:
        """Generate high-res hero image using OpenAI DALL-E 3 API."""
        print("[ImageGenerator] Calling OpenAI DALL-E 3 API...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "dall-e-3",
            "prompt": f"Professional high-end editorial tech photography: {prompt}",
            "n": 1,
            "size": "1792x1024",
            "quality": "standard"
        }
        resp = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        image_url = resp.json()["data"][0]["url"]

        img_data = requests.get(image_url, timeout=30).content
        filename = f"dalle_{int(time.time())}.png"
        filepath = self.output_dir / filename
        with open(filepath, "wb") as f:
            f.write(img_data)
        print(f"[ImageGenerator] Saved DALL-E image to {filepath}")
        return str(filepath)

    def _generate_stability(self, prompt: str, api_key: str) -> str:
        """Generate high-res hero image using Stability AI SDXL API."""
        print("[ImageGenerator] Calling Stability AI SDXL API...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        payload = {
            "prompt": prompt,
            "output_format": "webp",
            "aspect_ratio": "16:9",
            "mode": "text-to-image"
        }
        resp = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers=headers,
            files={"none": ""},
            data=payload,
            timeout=60
        )
        resp.raise_for_status()
        import base64
        image_b64 = resp.json().get("image")
        filename = f"stability_{int(time.time())}.webp"
        filepath = self.output_dir / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(image_b64))
        print(f"[ImageGenerator] Saved Stability image to {filepath}")
        return str(filepath)

    def _fallback_search(self, prompt: str) -> str:
        """Download a high-res royalty-free editorial image from DuckDuckGo."""
        print("[ImageGenerator] Searching editorial hero image via DuckDuckGo fallback...")
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        query = prompt.split(",")[0] if "," in prompt else prompt
        with DDGS() as ddgs:
            results = list(ddgs.images(f"{query} high resolution photography", max_results=3))
            for item in results:
                url = item.get("image")
                if url and url.startswith("http"):
                    try:
                        resp = requests.get(url, timeout=15)
                        if resp.status_code == 200:
                            ext = ".jpg" if "jpeg" in resp.headers.get("content-type", "") else ".png"
                            filename = f"hero_{int(time.time())}{ext}"
                            filepath = self.output_dir / filename
                            with open(filepath, "wb") as f:
                                f.write(resp.content)
                            print(f"[ImageGenerator] Downloaded fallback hero image to {filepath}")
                            return str(filepath)
                    except Exception:
                        continue
        raise RuntimeError("Failed to retrieve fallback hero image")
