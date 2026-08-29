import os
import re
from services.ollama_client import OllamaClient


class ImagePromptGenerator:

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv(
            "OLLAMA_MODEL",
            "qwen3:8b"
        )
        self.client = OllamaClient(self.model_name)

    def generate(self, topic: dict, article: dict) -> str:
        prompt = f"""You are an expert Stable Diffusion XL commercial product photographer.

Create a positive descriptive prompt for an ultra-high-end commercial featured image.

Product Subject: {topic.get("category", "")} - {topic.get("title", "")}
Context: {article.get("excerpt", "")[:200]}

CRITICAL SDXL RULES:
- Describe ONLY physical visual elements: product materials (brushed aluminum, matte polycarbonate, glass), studio lighting (softbox, edge rim light), surface (minimalist clean desk, marble countertop), and camera angle.
- DO NOT mention words like "no text", "no logos", "no watermark" in the positive prompt (negatives are handled separately).
- DO NOT include prices, numbers, years (e.g. $100, 2026), or SEO words like "review", "buying guide", "best".
- Keep the prompt under 50 words, focusing on commercial studio quality.

Return ONLY the raw prompt text with no explanation."""

        response = self.client.generate(prompt=prompt)
        raw_prompt = response.get("response", "").strip()

        # Sanitize prompt to eliminate any accidental text/price leakage
        cleaned = self._clean_prompt(raw_prompt, topic)
        print(f"Generated Clean Image Prompt: {cleaned}")
        return cleaned

    @staticmethod
    def _clean_prompt(prompt_text: str, topic: dict) -> str:
        """Strip negative words, prices, and SEO noise that trigger SDXL text generators."""
        # Remove quotes or markdown wrappers
        text = prompt_text.replace('"', '').replace('`', '').strip()
        if text.lower().startswith("prompt:"):
            text = text[7:].strip()

        # Remove negative phrases that accidentally trigger text drawing in CLIP
        neg_phrases = [
            r'\bno text\b', r'\bno logos?\b', r'\bno watermarks?\b', r'\bwithout text\b',
            r'\bno words\b', r'\bno letters\b', r'\bno people\b', r'\bunder \$\d+\b',
            r'\$\d+', r'\b20\d{2}\b', r'\breview\b', r'\bbuying guide\b', r'\bcomparison\b'
        ]
        for pat in neg_phrases:
            text = re.sub(pat, '', text, flags=re.IGNORECASE)

        # Collapse whitespace and trailing punctuation
        text = re.sub(r'\s{2,}', ' ', text).strip(' ,.-')
        if not text or len(text) < 15:
            cat = topic.get("category", "tech gadget")
            text = f"Commercial studio product photography of modern {cat}, clean minimalist aesthetic, soft studio lighting, high resolution, 8k"

        return text

    def unload(self) -> None:
        try:
            print("Unloading Ollama model...")
            self.client.unload()
            print("Ollama model unloaded.")
        except Exception as e:
            print(f"Warning: failed to unload Ollama model: {e}")