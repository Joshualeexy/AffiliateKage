import json
import os
import string
import time
from datetime import datetime
from typing import Any, Dict
from services.ollama_client import OllamaClient, extract_json
from services.prompt_loader import load_prompt
from generators.classifier import ArticleType
from research.base import ResearchReport

class ArticleGenerator:
    def __init__(self, model_name: str = None, max_retries: int = 3):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3:30b")
        self.max_retries = max_retries
        self.client = OllamaClient(self.model_name)

    def generate(self, topic: Dict[str, Any], article_type: ArticleType, outline: dict, research_report: ResearchReport = None) -> Dict[str, Any]:
        
        # Load the specific prompt for this article type
        prompt_name = f"article_{article_type.value}"
        try:
            prompt_template = string.Template(load_prompt(prompt_name))
        except Exception:
            # Fallback to a generic informational prompt if specific one is missing
            prompt_template = string.Template(load_prompt("article_informational"))

        research_context = ""
        if research_report and research_report.results:
            context_parts = []
            total_len = 0
            for idx, r in enumerate(research_report.results):
                part = f"--- Source {idx+1}: {r.title} ({r.url}) ---\n{r.content}"
                if total_len + len(part) > 4500:
                    remaining = 4500 - total_len
                    if remaining > 200:
                        context_parts.append(part[:remaining] + "\n[Truncated...]")
                    break
                context_parts.append(part)
                total_len += len(part)
            research_context = "RESEARCH CONTEXT:\n" + "\n\n".join(context_parts)

        outline_str = json.dumps(outline, indent=2)

        prompt = prompt_template.safe_substitute(
            title=topic.get("title", ""),
            category=topic.get("category", ""),
            primary_keyword=topic.get("primary_keyword", ""),
            secondary_keywords=", ".join(topic.get("secondary_keywords", [])),
            year=str(datetime.now().year),
            outline=outline_str,
            research_context=research_context,
            style_guide=load_prompt("style_guide")
        )

        for attempt in range(self.max_retries):
            try:
                response = self.client.generate(
                    prompt=prompt,
                    format="json",
                    options={"temperature": 0.6},
                )

                article = extract_json(response["response"])

                required = ["title", "excerpt", "seo_title", "meta_description", "content"]
                for field in required:
                    if not article.get(field):
                        raise ValueError(f"Missing {field}")

                # Truncate excerpt if it exceeds 500 characters
                excerpt = article.get("excerpt", "")
                if len(excerpt) > 500:
                    print(f"Warning: Generated excerpt is too long ({len(excerpt)} chars). Truncating to 500 chars.")
                    article["excerpt"] = excerpt[:497].rstrip() + "..."

                content = article["content"]
                word_count = len(content.split())
                if word_count < 500:
                    raise ValueError(f"Generated article is too short: {word_count} words")
                if "##" not in content:
                    raise ValueError("Generated article is missing Markdown H2 headings")

                return article

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}: {e}")
                time.sleep(1)
