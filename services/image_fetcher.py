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
    def fetch_product_data(cls, entities: List[Dict[str, Any]], max_items: int = 10) -> Dict[str, Dict[str, str]]:
        """Fetch clean product photo URLs and direct Amazon detail URLs for physical product entities.

        Returns:
            Dict mapping product_name -> {"image": image_url, "url": detail_page_url}
        """
        product_data: Dict[str, Dict[str, str]] = {}
        if not entities:
            return product_data

        product_entities = [
            e for e in entities
            if isinstance(e, dict)
            and e.get("is_physical") is not False
            and e.get("type", "").lower() in {"product", "physical_product"}
            and len(e.get("name", "").strip()) >= 3
        ]

        if not product_entities:
            return product_data

        target_entities = product_entities[:max_items]
        used_urls: set[str] = set()

        for entity in target_entities:
            name = entity["name"].strip()
            img_url = None
            direct_url = None

            # Strategy 1: Call Local Stealth Amazon Scraper API
            try:
                api_resp = requests.get(
                    f"{SCRAPER_API_URL}/api/search?q={quote_plus(name)}&limit=1",
                    timeout=12
                )
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    products = data.get("data", [])
                    if products:
                        item = products[0]
                        candidate = item.get("primaryImage")
                        if candidate and cls._is_valid_image_url(candidate, used_urls):
                            img_url = candidate
                            print(f"Image Fetcher [Custom Scraper API]: Found Amazon CDN image for '{name}' -> {img_url[:70]}...")
                        if item.get("detailPageUrl"):
                            direct_url = item["detailPageUrl"]
                            print(f"Image Fetcher [Custom Scraper API]: Found direct product URL for '{name}' -> {direct_url}")
            except Exception as e:
                logger.debug("Local custom scraper API unavailable for '%s': %s", name, e)

            # Strategy 2: Fallback to DDGS for image if API returned no image
            if not img_url:
                try:
                    try:
                        from ddgs import DDGS
                    except ImportError:
                        from duckduckgo_search import DDGS

                    search_query = f"{name} product photo"
                    with DDGS() as ddgs:
                        results = list(ddgs.images(
                            search_query,
                            max_results=5,
                            type_image="photo",
                        ))
                    for item in results:
                        candidate = item.get("image")
                        if candidate and cls._is_valid_image_url(candidate, used_urls):
                            img_url = candidate
                            print(f"Image Fetcher [DDGS Fallback]: Found image for '{name}' -> {img_url[:70]}...")
                            break
                except Exception as e:
                    logger.debug("DDGS image search failed for '%s': %s", name, e)

            if img_url:
                used_urls.add(img_url)

            product_data[name] = {
                "image": img_url or "",
                "url": direct_url or ""
            }

        return product_data

    @classmethod
    def fetch_product_images(cls, entities: List[Dict[str, Any]], max_items: int = 10) -> Dict[str, str]:
        """Fetch clean, unique product photo URLs for physical product entities.

        Returns:
            Dict mapping product_name -> image_url
        """
        data = cls.fetch_product_data(entities, max_items=max_items)
        return {name: info["image"] for name, info in data.items() if info.get("image")}

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
