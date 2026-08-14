import json
import re
import os
from pathlib import Path
from urllib.parse import quote_plus
from typing import Dict, List, Any

from services.ollama_client import OllamaClient
from services.prompt_loader import load_prompt


# Path to the generated topics file (fallback source of published posts)
TOPICS_PATH = Path(__file__).resolve().parent.parent / "generated_topics.json"

# Cache verified posts so we don't re-check every pipeline run
_verified_posts_cache: list | None = None


class InternalLinkInjector:
    """Injects validated internal links into article Markdown content.

    Works in three steps:
    1. Fetch & score: get published posts, score relevance to current article.
    2. LLM injection:  ask the model to weave 1-3 links naturally into the text.
    3. Strip fakes:    remove any hallucinated internal links that slipped through.
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
        """Run the full internal-link injection pipeline.

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

        # Step B: Ask the LLM to inject links
        content = self._llm_inject(content, top_posts)

        # Step C: Strip any hallucinated internal links
        valid_slugs = {p["slug"] for p in published}
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
            # API returned data; normalize it
            normalized = []
            for p in posts:
                title = p.get("title", "").strip()
                slug = p.get("slug", "") or self._slugify(title)
                if title:
                    normalized.append({"title": title, "slug": slug})
            _verified_posts_cache = normalized
            print(f"Internal Link Injector: Loaded {len(normalized)} posts from API.")
            return normalized

        # Fallback: read generated_topics.json and verify via topic_exists
        print("Internal Link Injector: API endpoint not available. Using fallback.")
        return self._fallback_get_posts(api_client)

    def _fallback_get_posts(self, api_client: Any) -> list:
        """Read topics from file and verify each via topic_exists API."""
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
            title = t.get("title", "").strip()
            if not title:
                continue
            try:
                if api_client.topic_exists(title):
                    verified.append({
                        "title": title,
                        "slug": self._slugify(title),
                    })
            except Exception:
                # API error on this check; skip this topic
                continue

        _verified_posts_cache = verified
        print(f"Internal Link Injector: Verified {len(verified)} published posts via fallback.")
        return verified

    def _score_candidates(
        self,
        candidates: list,
        topic: Dict[str, Any],
        entities: List[Dict[str, str]],
    ) -> list:
        """Score candidates by keyword overlap with the current article."""

        # Build the keyword set from the current article
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

        # Remove common stop words that would inflate scores
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

        # Score each candidate
        scored = []
        for candidate in candidates:
            title_lower = candidate["title"].lower()
            title_words_set = set(title_lower.split())
            overlap = len(keywords & title_words_set)
            if overlap > 0:
                scored.append({**candidate, "_score": overlap})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored

    # ── Step B: LLM Injection ─────────────────────────────────────

    def _llm_inject(self, content: str, top_posts: list) -> str:
        """Ask the LLM to inject internal links into the article."""
        related_posts_str = "\n".join(
            f"- {p['title']} | {self.BLOG_BASE}/{p['slug']}"
            for p in top_posts
        )

        try:
            prompt = load_prompt(
                "internal_links",
                article_content=content,
                related_posts=related_posts_str,
            )
        except FileNotFoundError:
            # Inline fallback if prompt file is missing
            prompt = (
                f"Read this article and inject 1-3 internal links from the list below.\n"
                f"Use descriptive anchor text. Return ONLY the modified article.\n\n"
                f"ARTICLE:\n{content}\n\n"
                f"RELATED POSTS:\n{related_posts_str}\n"
            )

        try:
            response = self.client.generate(
                prompt=prompt,
                options={"temperature": 0.3},
            )
            result = response.get("response", "").strip()

            # Basic sanity: result should still look like a Markdown article
            if len(result) < len(content) * 0.5:
                print("Internal Link Injector: LLM response too short. Keeping original.")
                return content

            if "##" not in result:
                print("Internal Link Injector: LLM response missing headings. Keeping original.")
                return content

            return result

        except Exception as e:
            print(f"Internal Link Injector: LLM call failed: {e}. Keeping original.")
            return content

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
    def _slugify(title: str) -> str:
        """Convert a title to a URL slug matching the blog's format."""
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)   # Remove special chars except hyphens
        slug = re.sub(r'[\s_]+', '-', slug)     # Spaces/underscores to hyphens
        slug = re.sub(r'-+', '-', slug)         # Collapse multiple hyphens
        slug = slug.strip('-')
        return slug
