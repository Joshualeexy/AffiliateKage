import logging
import os
import random
import time
from typing import Dict, List, Any
from urllib.parse import quote_plus
import requests

logger = logging.getLogger(__name__)

SCRAPER_API_URL = os.getenv("CUSTOM_SCRAPER_API_URL", "http://127.0.0.1:4000")


class ImageFetcher:
    """Fetches high-quality, authentic product photos.
    
    Priority:
      1. Local Stealth Amazon Scraper API (http://127.0.0.1:4000)
         - Direct Amazon CDN images
         - Official product matches
      2. Fallback to DDGS image search if API is unreachable.
    """

    BAD_URL_KEYWORDS = [
        "youtube", "tiktok", "facebook", "instagram", "pinterest", "twitter", "x.com",
        "logo", "icon", "favicon", "avatar", "badge", "banner", "spinner",
        "placeholder", "pixel", "transparent", ".svg", "data:image",
    ]

    @classmethod
    def fetch_product_images(cls, entities: List[Dict[str, Any]], max_items: int = 10) -> Dict[str, str]:
        """Fetch clean, unique product photo URLs for physical product entities.

        Args:
            entities: List of entity dicts from the entity extractor.
            max_items: Maximum number of products to fetch images for (default 10).

        Returns:
            Dict mapping product_name -> image_url
        """
        product_images: Dict[str, str] = {}
        if not entities:
            return product_images

        # Filter for genuine physical product entities only
        product_entities = [
            e for e in entities
            if isinstance(e, dict)
            and e.get("is_physical") is not False
            and e.get("type", "").lower() in {"product", "physical_product"}
            and len(e.get("name", "").strip()) >= 3
        ]

        if not product_entities:
            return product_images

        target_entities = product_entities[:max_items]
        used_urls: set[str] = set()

        for entity in target_entities:
            name = entity["name"].strip()
            img_url = None

            # Strategy 1: Call Local Stealth Amazon Scraper API
            try:
                api_resp = requests.get(
                    f"{SCRAPER_API_URL}/api/search?q={quote_plus(name)}&limit=1",
                    timeout=12
                )
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    products = data.get("data", [])
                    if products and products[0].get("primaryImage"):
                        candidate = products[0]["primaryImage"]
                        if cls._is_valid_image_url(candidate, used_urls):
                            img_url = candidate
                            print(f"Image Fetcher [Custom Scraper API]: Found Amazon CDN image for '{name}' -> {img_url[:70]}...")
            except Exception as e:
                logger.debug("Local custom scraper API unavailable for '%s': %s", name, e)

            # Strategy 2: Fallback to DDGS
            if not img_url:
                try:
                    try:
                        from ddgs import DDGS
                    except ImportError:
                        from duckduckgo_search import DDGS

                    with DDGS() as ddgs:
                        query = f"{name} product photo white background"
                        results = list(ddgs.images(query, max_results=3))
                        for item in results:
                            candidate = item.get("image") or item.get("thumbnail")
                            if candidate and cls._is_valid_image_url(candidate, used_urls):
                                img_url = candidate
                                print(f"Image Fetcher [DDGS Fallback]: Found photo for '{name}' -> {img_url[:70]}...")
                                break
                except Exception as e:
                    logger.warning("DDGS fallback failed for '%s': %s", name, e)

            if img_url:
                product_images[name] = img_url
                used_urls.add(img_url)

            # Natural small pause between items
            time.sleep(random.uniform(0.5, 1.0))

        return product_images

    @classmethod
    def _is_valid_image_url(cls, url: str, used_urls: set[str]) -> bool:
        """Validate that an image URL is clean, unique, and not a logo or tracking badge."""
        if not url or not isinstance(url, str):
            return False
        url_lower = url.lower()
        if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
            return False
        if url in used_urls:
            return False
        if any(bad in url_lower for bad in cls.BAD_URL_KEYWORDS):
            return False
        return True
