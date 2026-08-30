import json
import re
import os
from pathlib import Path
from typing import Dict, List, Any

from services.ollama_client import OllamaClient, extract_json
from services.prompt_loader import load_prompt


# Path to the generated topics file (fallback source of published posts)
TOPICS_PATH = Path(__file__).resolve().parent.parent / "generated_topics.json"

# Cache verified posts so we don't re-check every pipeline run
_verified_posts_cache: list | None = None


class InternalLinkInjector:
    """Injects validated internal links into article Markdown content.

    Works in three targeted steps:
    1. Fetch & score: get published posts, score relevance to current article.
    2. LLM extraction: ask the model for 1-3 targeted link placements as JSON.
    3. Deterministic injection: perform safe, exact substring replacements in Python.
    """

    SITE_DOMAIN = "ejiroinspire.com"
    BLOG_BASE = f"https://{SITE_DOMAIN}/blog"

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5")
        self.client = OllamaClient(self.model_name)

    # ── Public API ────────────────────────────────────────────────

    def inject(
        self,
        content: str,
        topic: Dict[str, Any],
        entities: List[Dict[str, str]],
        api_client: Any,
    ) -> str:
        """Run the targeted internal-link injection pipeline.

        Args:
            content:    Article Markdown (post-validation, pre-HTML).
            topic:      The current article's topic dict.
            entities:   Extracted entities from the article.
            api_client: An ApiClient instance for fetching/verifying posts.

        Returns:
            Modified Markdown with valid internal links injected.
        """
        # Step A: Get verified published posts and score them
        published = self._get_published_posts(api_client)
        if not published:
            print("Internal Link Injector: No published posts found. Skipping.")
            return content

        # Remove the current article from candidates
        current_title_lower = topic.get("title", "").lower().strip()
        candidates = [
            p for p in published
            if p["title"].lower().strip() != current_title_lower
        ]

        if not candidates:
            print("Internal Link Injector: No other published posts. Skipping.")
            return content

        scored = self._score_candidates(candidates, topic, entities)
        top_posts = scored[:10]

        if not top_posts:
            print("Internal Link Injector: No relevant posts found. Skipping.")
            return content

        valid_slugs = {p["slug"] for p in published}

        # Step B: Get targeted JSON placements from LLM and inject deterministically
        content = self._json_inject(content, top_posts, valid_slugs)

        # Step C: Extra safety strip for any hallucinated links
        content = self._strip_hallucinated_links(content, valid_slugs)

        return content

    # ── Step A: Fetch & Score ─────────────────────────────────────

    def _get_published_posts(self, api_client: Any) -> list:
        """Get published posts, trying API first then falling back to file + verify."""
        global _verified_posts_cache
        if _verified_posts_cache is not None:
            return _verified_posts_cache

        # Try the dedicated API endpoint first
        posts = None
        try:
            posts = api_client.get_published_posts()
        except Exception as e:
            print(f"Internal Link Injector: API endpoint failed: {e}")

        if posts is not None:
            normalized = []
            for p in posts:
                title = p.get("title", "").strip()
                slug = p.get("slug", "") or self._slugify(title)
                if title:
                    normalized.append({"title": title, "slug": slug})
            _verified_posts_cache = normalized
            print(f"Internal Link Injector: Loaded {len(normalized)} posts from API.")
            return normalized

        # Fallback: read generated_topics.json
        print("Internal Link Injector: API endpoint not available. Using fallback.")
        return self._fallback_get_posts(api_client)

    def _fallback_get_posts(self, api_client: Any) -> list:
        """Read published topics from generated_topics.json."""
        global _verified_posts_cache

        if not TOPICS_PATH.exists():
            print(f"Internal Link Injector: {TOPICS_PATH} not found.")
            return []

        try:
            topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Internal Link Injector: Failed to read topics file: {e}")
            return []

        verified = []
        for t in topics:
            if isinstance(t, dict):
                title = t.get("title", "").strip()
            elif isinstance(t, str):
                title = t.strip()
            else:
                continue

            if title:
                verified.append({
                    "title": title,
                    "slug": self._slugify(title),
                })

        _verified_posts_cache = verified
        print(f"Internal Link Injector: Loaded {len(verified)} published posts from local topics database.")
        return verified

    def _score_candidates(
        self,
        candidates: list,
        topic: Dict[str, Any],
        entities: List[Dict[str, str]],
    ) -> list:
        """Score candidates by keyword overlap with the current article."""
        keywords: set[str] = set()

        title_words = topic.get("title", "").lower().split()
        keywords.update(w for w in title_words if len(w) > 2)

        pk = topic.get("primary_keyword", "").lower()
        if pk:
            keywords.update(w for w in pk.split() if len(w) > 2)

        for sk in topic.get("secondary_keywords", []):
            keywords.update(w for w in sk.lower().split() if len(w) > 2)

        category = topic.get("category", "").lower()
        if category:
            keywords.update(w for w in category.split() if len(w) > 2)

        for entity in entities:
            name = entity.get("name", "").lower() if isinstance(entity, dict) else ""
            keywords.update(w for w in name.split() if len(w) > 2)

        stop_words = {
            "the", "and", "for", "with", "you", "your", "that", "this",
            "from", "are", "how", "what", "which", "best", "top", "our",
            "has", "have", "will", "can", "its", "not", "but", "was",
            "were", "been", "more", "most", "very", "just", "also",
            "into", "than", "then", "when", "where", "why", "all",
            "each", "every", "both", "few", "some", "any", "other",
            "about", "over", "under", "between", "through", "during",
        }
        keywords -= stop_words

        if not keywords:
            return candidates

        scored = []
        for candidate in candidates:
            title_lower = candidate["title"].lower()
            title_words_set = set(title_lower.split())
            overlap = len(keywords & title_words_set)
            if overlap > 0:
                scored.append({**candidate, "_score": overlap})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored

    # ── Step B: Targeted JSON Extraction & Python Replacement ─────

    def _json_inject(self, content: str, top_posts: list, valid_slugs: set) -> str:
        """Extract anchor placements as JSON and inject links safely via Python."""
        # Create a lightweight overview (headings + first few paragraphs)
        lines = content.split('\n')
        overview_lines = []
        para_count = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                overview_lines.append(stripped)
            elif stripped and para_count < 4:
                overview_lines.append(stripped)
                para_count += 1

        overview_text = '\n'.join(overview_lines)[:2000]

        related_posts_str = "\n".join(
            f"- {p['title']} | Slug: {p['slug']}"
            for p in top_posts
        )

        try:
            prompt = load_prompt(
                "internal_links",
                article_overview=overview_text,
                related_posts=related_posts_str,
            )
        except Exception:
            prompt = (
                f"Identify 1-3 internal link placements from the related posts list.\n"
                f"ARTICLE OVERVIEW:\n{overview_text}\n\n"
                f"RELATED POSTS:\n{related_posts_str}\n\n"
                f"Return ONLY valid JSON: {{\"placements\": [{{\"target_phrase\": \"phrase in text\", \"slug\": \"slug\", \"anchor_text\": \"anchor\"}}]}}"
            )

        try:
            response = self.client.generate(
                prompt=prompt,
                format="json",
                options={"temperature": 0.1},
            )
            data = extract_json(response.get("response", ""))
            placements = data.get("placements", []) if isinstance(data, dict) else []

            injected_count = 0
            for placement in placements:
                if not isinstance(placement, dict):
                    continue
                target_phrase = placement.get("target_phrase", "").strip()
                slug = placement.get("slug", "").strip()
                anchor_text = placement.get("anchor_text", "").strip() or target_phrase

                if not target_phrase or not slug or slug not in valid_slugs:
                    continue

                if injected_count >= 3:
                    break

                # Attempt safe deterministic line replacement
                new_content, replaced = self._replace_target_phrase(content, target_phrase, slug, anchor_text)
                if replaced:
                    content = new_content
                    injected_count += 1
                    print(f"Internal Link Injector: Injected link for '{anchor_text}' -> /blog/{slug}")

            return content

        except Exception as e:
            print(f"Internal Link Injector: Targeted JSON injection failed: {e}. Keeping content unchanged.")
            return content

    @classmethod
    def _replace_target_phrase(cls, content: str, target_phrase: str, slug: str, anchor_text: str) -> tuple[str, bool]:
        """Safely replaces the first occurrence of target_phrase that is outside headings, links, code, and tables."""
        url = f"{cls.BLOG_BASE}/{slug}"
        link_md = f"[{anchor_text}]({url})"

        lines = content.split('\n')
        in_code_block = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue

            if in_code_block or stripped.startswith('#') or '|' in stripped:
                continue

            # Skip if target_phrase is not in this line
            pattern = re.compile(rf'\b({re.escape(target_phrase)})\b', re.IGNORECASE)
            match = pattern.search(line)
            if not match:
                continue

            idx = match.start(1)
            end_idx = match.end(1)

            # Ensure we're not inside an existing markdown link: [ ... ] or ( ... )
            before = line[:idx]
            if '[' in before:
                last_open_bracket = before.rfind('[')
                between = before[last_open_bracket:]
                if '](' not in between and ')' not in between:
                    continue
                if '](' in between and ')' not in between:
                    continue

            # Replace this single line
            lines[i] = line[:idx] + link_md + line[end_idx:]
            return '\n'.join(lines), True

        return content, False

    # ── Step C: Strip hallucinated links ──────────────────────────

    def _strip_hallucinated_links(self, content: str, valid_slugs: set) -> str:
        """Remove any ejiroinspire.com internal links whose slug is not in valid_slugs."""
        domain_pattern = re.compile(
            r'\[([^\]]+)\]\(https?://(?:www\.)?ejiroinspire\.com/blog/([^)\s]+)\)'
        )

        def _check_link(match: re.Match) -> str:
            anchor = match.group(1)
            slug = match.group(2).rstrip("/")
            if slug in valid_slugs:
                return match.group(0)  # Keep valid link
            print(f"Internal Link Injector: Stripped hallucinated link -> /blog/{slug}")
            return anchor  # Replace link with just the anchor text

        return domain_pattern.sub(_check_link, content)

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _slugify(title: str, evergreen: bool = True) -> str:
        """Convert a title to a URL slug matching the blog's format."""
        slug = title.lower().strip()
        if evergreen:
            slug = re.sub(r'\b20\d{2}\b', '', slug)
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')
