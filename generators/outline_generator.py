import json
import string
from datetime import datetime
from services.ollama_client import OllamaClient, extract_json
from services.prompt_loader import load_prompt
from generators.classifier import ArticleType

class OutlineGenerator:
    def __init__(self):
        self.client = OllamaClient()

    def generate(self, topic: dict, article_type: ArticleType, research_report=None) -> dict:
        """Generate a structured outline for the given topic."""
        # We will load the outline prompt. We might not have it saved, so I will fall back
        try:
            prompt_template = string.Template(load_prompt("outline"))
            research_context = ""
            if research_report and research_report.results:
                context_parts = []
                total_len = 0
                for idx, r in enumerate(research_report.results):
                    part = f"--- Source {idx+1}: {r.title} ({r.url}) ---\n{r.content}"
                    if total_len + len(part) > 3000:
                        remaining = 3000 - total_len
                        if remaining > 200:
                            context_parts.append(part[:remaining] + "\n[Truncated...]")
                        break
                    context_parts.append(part)
                    total_len += len(part)
                research_context = "RESEARCH CONTEXT:\n" + "\n\n".join(context_parts)
                
            prompt = prompt_template.safe_substitute(
                title=topic.get("title", ""),
                article_type=article_type.value,
                category=topic.get("category", ""),
                primary_keyword=topic.get("primary_keyword", ""),
                secondary_keywords=", ".join(topic.get("secondary_keywords", [])),
                year=str(datetime.now().year),
                research_context=research_context
            )
        except Exception:
            # Fallback if outline.txt is missing
            prompt = (
                f"Create a detailed article outline for: '{topic.get('title')}'\n"
                f"Type: {article_type.value}\n"
                f"Return ONLY valid JSON with a 'sections' list."
            )

        try:
            response = self.client.generate(prompt=prompt, format="json", options={"temperature": 0.4})
            return extract_json(response["response"])
        except Exception as e:
            print(f"Outline generation failed: {e}")
            return {"sections": []}
