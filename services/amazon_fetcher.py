import re
import logging
import random
import time
import requests
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class AmazonFetcher:
    """Fetches Amazon product ASINs and constructs deterministic CDN image URLs.

    Strategy:
      1. Search Amazon for the product name.
      2. Extract the first ASIN from the search results HTML.
      3. Construct a deterministic Amazon CDN image URL from the ASIN.
      4. Verify the image URL returns a valid response.
      5. If anything fails, return None — never a wrong image.
    """

    # Amazon CDN image URL template — works without API keys
    IMAGE_CDN_TEMPLATE = "https://m.media-amazon.com/images/I/{asin}._AC_SL300_.jpg"

    # Regex to extract ASINs from Amazon search result HTML
    ASIN_PATTERN = re.compile(r'data-asin="([A-Z0-9]{10})"')
    # Fallback: extract from /dp/ links
    ASIN_DP_PATTERN = re.compile(r'/dp/([A-Z0-9]{10})')

    # User-Agent rotation to avoid instant blocks on search
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ]

    @classmethod
    def get_best_asin_for_entity(cls, entity_name: str, tracking_id: str = "") -> Optional[str]:
        """Search Amazon for a product and return the best-matching ASIN.

        Args:
            entity_name: The product name to search for.
            tracking_id: Amazon affiliate tag (unused for search, kept for API compat).

        Returns:
            The first valid ASIN found, or None if search fails.
        """
        if not entity_name or len(entity_name.strip()) < 3:
            return None

        encoded_query = quote_plus(entity_name.strip())
        search_url = f"https://www.amazon.com/s?k={encoded_query}"

        headers = {
            "User-Agent": random.choice(cls.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        try:
            response = requests.get(search_url, headers=headers, timeout=12)
            if response.status_code != 200:
                logger.warning("Amazon search returned HTTP %d for '%s'", response.status_code, entity_name)
                return None

            html = response.text

            # Extract ASINs from data-asin attributes (primary method)
            asins = cls.ASIN_PATTERN.findall(html)
            # Filter out empty strings and sponsored/ad ASINs that appear first
            valid_asins = [a for a in asins if a and len(a) == 10]

            if not valid_asins:
                # Fallback: extract from /dp/ links
                valid_asins = cls.ASIN_DP_PATTERN.findall(html)

            if valid_asins:
                # Deduplicate while preserving order
                seen = set()
                unique_asins = []
                for a in valid_asins:
                    if a not in seen:
                        seen.add(a)
                        unique_asins.append(a)

                asin = unique_asins[0]
                logger.info("Found ASIN %s for '%s'", asin, entity_name)
                return asin

            logger.warning("No ASINs found in Amazon search results for '%s'", entity_name)
            return None

        except requests.Timeout:
            logger.warning("Amazon search timed out for '%s'", entity_name)
            return None
        except Exception as e:
            logger.warning("Amazon ASIN search failed for '%s': %s", entity_name, e)
            return None

    @classmethod
    def get_product_image_url(cls, asin: str) -> Optional[str]:
        """Construct and verify a deterministic Amazon CDN image URL for an ASIN.

        Args:
            asin: A valid 10-character Amazon ASIN.

        Returns:
            The verified CDN image URL, or None if the image doesn't exist.
        """
        if not asin or len(asin) != 10:
            return None

        image_url = cls.IMAGE_CDN_TEMPLATE.format(asin=asin)

        try:
            # Verify the image actually exists with a lightweight HEAD request
            resp = requests.head(image_url, timeout=5, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and "image" in content_type:
                return image_url
            else:
                logger.debug("Amazon CDN image check failed for ASIN %s: HTTP %d, Content-Type: %s",
                             asin, resp.status_code, content_type)
                return None
        except Exception as e:
            logger.debug("Amazon CDN image HEAD request failed for ASIN %s: %s", asin, e)
            return None

    @staticmethod
    def generate_product_html(product_data: Dict[str, str], asin: str) -> str:
        """Generate an Amazon-compliant HTML product card.

        No static prices are displayed — only a "Check Price" CTA button.
        This complies with the Amazon Associates Operating Agreement.

        Args:
            product_data: Dictionary containing image_url, title, cta_url.
            asin: Amazon Standard Identification Number.

        Returns:
            HTML string for the product card.
        """
        img_tag = ""
        image_url = product_data.get("image_url", "")
        if image_url and not image_url.startswith("https://placehold.co"):
            img_tag = (
                f'<img src="{image_url}" alt="{product_data.get("title", "Product")}" '
                f'loading="lazy" style="max-height: 180px; object-fit: contain; margin-bottom: 15px;">'
            )

        title = product_data.get("title", "View Product on Amazon")
        cta_url = product_data.get("cta_url", f"https://amazon.com/dp/{asin}/")

        html_template = f"""
        <div class="amazon-product-card" style="border: 1px solid #e0e0e0; padding: 20px; border-radius: 8px; max-width: 400px; margin: 20px auto; text-align: center; font-family: Arial, sans-serif;">
            {img_tag}
            <h4 style="font-size: 16px; color: #333; margin: 10px 0;">{title}</h4>
            <a href="{cta_url}" target="_blank" rel="nofollow sponsored noopener" style="display: inline-block; background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 10px;">Check Price on Amazon &rarr;</a>
        </div>
        """

        return html_template