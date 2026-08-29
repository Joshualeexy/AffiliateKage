import re
from typing import List, Dict, Any

class AffiliateLinkInjector:
    """Injects/replaces links matching configured patterns with affiliate redirect URLs."""

    PROTECTED_DOMAINS = ["ejiroinspire.com"]

    def inject(self, html_content: str, mappings: List[Dict[str, Any]]) -> str:
        """Replace matching URLs inside href attributes with the mapped affiliate URLs.
        
        Args:
            html_content: The HTML content of the article.
            mappings: A list of affiliate link dicts, each having 'pattern' and 'url'.
            
        Returns:
            The modified HTML content.
        """
        if not html_content or not mappings:
            return html_content

        def replace_link(match: re.Match) -> str:
            quote = match.group(1)
            url = match.group(2)
            url_lower = url.lower()
            
            # Protect internal links, relative links, and anchor jumps
            if any(dom in url_lower for dom in self.PROTECTED_DOMAINS) or url.startswith(("/", "#")):
                return match.group(0)

            # Find a matching mapping where pattern is a substring of the URL
            for mapping in mappings:
                pattern = mapping.get("pattern")
                affiliate_url = mapping.get("url")
                if pattern and affiliate_url and pattern.lower() in url_lower:
                    if url == affiliate_url:
                        return match.group(0)
                    print(f"Affiliate Link Injector: Matched pattern '{pattern}' on URL '{url}' -> replacing with '{affiliate_url}'")
                    return f'href={quote}{affiliate_url}{quote}'
            return match.group(0)

        # Match href="http(s)://..." or href='http(s)://...'
        html_content = re.sub(
            r'href=(["\'])(https?://[^\s"\'<>]+)\1',
            replace_link,
            html_content,
            flags=re.IGNORECASE
        )

        return html_content
