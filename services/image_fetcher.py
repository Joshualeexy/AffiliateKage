import logging
from typing import Dict, List, Any
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class ImageFetcher:
    """Fetches high-quality, authentic product photos and editorial stock photos."""

    @staticmethod
    def fetch_product_images(entities: List[Dict[str, Any]], max_items: int = 3) -> Dict[str, str]:
        """Fetch clean product photo URLs for physical product entities.
        
        Returns:
            Dict mapping product_name -> image_url
        """
        product_images: Dict[str, str] = {}
        if not entities:
            return product_images

        product_entities = [
            e for e in entities
            if isinstance(e, dict) and e.get("type", "").lower() == "product" and len(e.get("name", "").strip()) > 3
        ]

        if not product_entities:
            return product_images

        # Search for top product entities
        target_entities = product_entities[:max_items]

        try:
            with DDGS() as ddgs:
                for entity in target_entities:
                    name = entity["name"].strip()
                    query = f"{name} product photo white background"
                    try:
                        results = list(ddgs.images(query, max_results=2))
                        if results:
                            # Prefer images from reputable direct CDNs or clean image URLs
                            img_url = results[0].get("image")
                            if img_url and img_url.startswith("http") and not any(bad in img_url for bad in ["youtube", "tiktok", "facebook"]):
                                product_images[name] = img_url
                                print(f"Image Fetcher: Found product photo for '{name}' -> {img_url[:60]}...")
                    except Exception as e:
                        logger.warning("Failed to fetch image for '%s': %s", name, e)
        except Exception as e:
            print(f"Image Fetcher: Search session failed: {e}")

        return product_images
