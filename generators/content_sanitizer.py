import re
import os
from urllib.parse import quote_plus
from typing import List, Dict, Any


class ContentSanitizer:
    """Post-processing sanitizer for LLM-generated article content.
    
    Fixes formatting issues (dashes, bold-as-heading, heading spacing),
    enforces smart entity linking (Amazon for physical goods, homepage/clean links for software),
    and generates visual product callout cards.
    """

    NON_PHYSICAL_CATEGORIES = {
        "web services",
        "digital security",
        "creative software",
        "productivity software",
        "ai tools",
        "personal finance",
        "saving money",
        "remote work",
        "career & productivity",
        "education & learning",
        "solo & group travel",
        "productivity & habits",
    }

    DIGITAL_KEYWORDS = {
        "app", "apps", "software", "vpn", "hosting", "domain", "domains",
        "registrar", "registrars", "cloud", "builder", "builders", "platform",
        "extension", "plugin", "subscription", "api", "saas", "template",
        "website", "service", "services", "tool", "tools", "bot", "ai",
    }

    KNOWN_DIGITAL_SERVICES = {
        "monarch money", "ynab", "pocketguard", "personal capital", "copilot", "copilot money",
        "goodbudget", "truebill", "spendee", "wally", "mint", "namecheap", "godaddy",
        "google domains", "hostinger", "bluehost", "siteground", "resume builder",
        "duolingo", "babbel", "rosetta stone", "notion", "evernote", "todoist",
        "trello", "asana", "slack", "zoom", "canva", "adobe", "nordvpn", "expressvpn",
        "surfshark", "1password", "bitwarden", "lastpass", "protonmail", "dashlane",
        "eat this much", "mealime", "yummly", "plan to eat", "myfitnesspal", "tripit",
    }

    # Curated mapping of known software/SaaS entities to their official homepage URLs
    KNOWN_SOFTWARE_URLS = {
        "monarch money": "https://www.monarchmoney.com",
        "ynab": "https://www.ynab.com",
        "pocketguard": "https://pocketguard.com",
        "personal capital": "https://www.personalcapital.com",
        "copilot": "https://copilot.money",
        "copilot money": "https://copilot.money",
        "goodbudget": "https://goodbudget.com",
        "truebill": "https://www.truebill.com",
        "spendee": "https://www.spendee.com",
        "wally": "https://wally.me",
        "mint": "https://mint.intuit.com",
        "namecheap": "https://www.namecheap.com",
        "godaddy": "https://www.godaddy.com",
        "google domains": "https://domains.google",
        "hostinger": "https://www.hostinger.com",
        "bluehost": "https://www.bluehost.com",
        "siteground": "https://www.siteground.com",
        "duolingo": "https://www.duolingo.com",
        "babbel": "https://www.babbel.com",
        "rosetta stone": "https://www.rosettastone.com",
        "notion": "https://www.notion.so",
        "evernote": "https://evernote.com",
        "todoist": "https://todoist.com",
        "trello": "https://trello.com",
        "asana": "https://asana.com",
        "slack": "https://slack.com",
        "zoom": "https://zoom.us",
        "canva": "https://www.canva.com",
        "adobe": "https://www.adobe.com",
        "nordvpn": "https://nordvpn.com",
        "expressvpn": "https://www.expressvpn.com",
        "surfshark": "https://surfshark.com",
        "1password": "https://1password.com",
        "bitwarden": "https://bitwarden.com",
        "lastpass": "https://www.lastpass.com",
        "protonmail": "https://proton.me",
        "dashlane": "https://www.dashlane.com",
        "eat this much": "https://www.eatthismuch.com",
        "mealime": "https://www.mealime.com",
        "yummly": "https://www.yummly.com",
        "plan to eat": "https://www.plantoeat.com",
        "myfitnesspal": "https://www.myfitnesspal.com",
        "tripit": "https://www.tripit.com",
    }

    def __init__(self):
        self.affiliate_tag = os.getenv("AMAZON_AFFILIATE_TAG", "")

    def sanitize_plain_text(self, text: str) -> str:
        """Strip all Markdown bold and italic markers from plain text fields."""
        if not text:
            return text
        text = re.sub(r'[\*_]{1,2}([^*_]+)[\*_]{1,2}', r'\1', text)
        for marker in ["**", "__", "*", "_"]:
            text = text.replace(marker, "")
        return text.strip()

    def sanitize(self, content: str, article_type: str | None = None) -> str:
        """Run all formatting sanitization steps on article Markdown content."""
        content = self._remove_dashes(content)
        
        is_tutorial = False
        if article_type is not None:
            if hasattr(article_type, "value"):
                is_tutorial = article_type.value == "tutorial"
            else:
                is_tutorial = str(article_type).lower().strip() == "tutorial"

        if not is_tutorial:
            content = self._unwrap_code_blocks(content)
            
        content = self._strip_markdown_markers_from_headings(content)
        content = self._fix_bold_headings(content)
        content = self._split_inlined_lists(content)
        content = self._fix_heading_spacing(content)
        return content

    def _is_digital_or_non_physical(self, entity: dict, category: str = "") -> bool:
        """Determine if an entity is a digital service, software, app, or non-physical product."""
        if not isinstance(entity, dict):
            return True

        if entity.get("is_physical") is False:
            return True

        category_lower = category.lower().strip()
        if category_lower in self.NON_PHYSICAL_CATEGORIES:
            return True

        etype = entity.get("type", "").lower().strip()
        if etype in {"software", "service", "company", "app", "website", "publisher"}:
            return True

        name = entity.get("name", "").lower().strip()
        if not name:
            return True

        if name in self.KNOWN_DIGITAL_SERVICES:
            return True

        name_words = set(re.findall(r'\b[a-z]+\b', name))
        if name_words & self.DIGITAL_KEYWORDS:
            return True

        return False

    def enforce_amazon_links(self, content: str, entities: list, category: str = "") -> str:
        """Smart entity link injection:
        - Wraps physical product entities in Amazon search links (with affiliate tag).
        - Avoids forcing software, SaaS, or non-physical items into Amazon search URLs.
        """
        # Step 1: Strip any explicit "Check Price on Amazon" style links generated by the LLM
        content = re.sub(
            r'\s*[\*\_]*\s*\[(?:Check Price on Amazon|Buy on Amazon|Check on Amazon|Amazon|Check Price)\]\(https?://[^)\s]+\)\s*[\*\_]*',
            '',
            content,
            flags=re.IGNORECASE
        )

        # Step 1b: Strip any Amazon search links mistakenly applied to software/non-physical items
        content = self.strip_unwanted_amazon_links(content, category=category)

        # Filter to only physical product entities (skip software/companies/digital tools)
        product_entities = [
            e for e in entities
            if isinstance(e, dict)
            and len(e.get("name", "").strip()) >= 3
            and not self._is_digital_or_non_physical(e, category)
        ]

        for entity in product_entities:
            entity_name = entity.get("name", "").strip()
            if not entity_name:
                continue

            # Build the Amazon search URL
            encoded_name = quote_plus(entity_name)
            amazon_url = f"https://www.amazon.com/s?k={encoded_name}"
            if self.affiliate_tag:
                amazon_url += f"&tag={self.affiliate_tag}"

            content = self._wrap_entity_in_link(content, entity_name, amazon_url)

        # Append affiliate tag to any existing Amazon links that lack one
        if self.affiliate_tag:
            content = self._append_affiliate_tag(content)

        return content

    def strip_unwanted_amazon_links(self, content: str, category: str = "") -> str:
        """Strip or convert Amazon search links that were erroneously applied to software or non-physical items."""
        category_lower = category.lower().strip()
        is_non_physical_cat = category_lower in self.NON_PHYSICAL_CATEGORIES

        def _clean_link(match: re.Match) -> str:
            anchor_text = match.group(1).strip()
            lower_anchor = anchor_text.lower()

            is_digital = (
                is_non_physical_cat
                or lower_anchor in self.KNOWN_DIGITAL_SERVICES
                or any(kw in lower_anchor for kw in [
                    "app", "software", "vpn", "hosting", "domain", "saas",
                    "kids", "academy", "lift", "tool", "platform", "bot",
                ])
            )

            if is_digital:
                homepage = self.KNOWN_SOFTWARE_URLS.get(lower_anchor)
                if homepage:
                    return f"[{anchor_text}]({homepage})"
                return anchor_text

            return match.group(0)

        return re.sub(
            r'\[([^\]]+)\]\(https?://(?:www\.)?amazon\.com/s\?k=[^)\s]+\)',
            _clean_link,
            content,
            flags=re.IGNORECASE
        )

    def enforce_software_links(self, content: str, entities: list, category: str = "", affiliate_links: list = None) -> str:
        """Wrap software/digital entities in their official homepage URLs.

        Uses the curated KNOWN_SOFTWARE_URLS mapping first, then falls back
        to affiliate link patterns from the backend, then skips silently.
        Physical products are never touched by this method.
        """
        affiliate_links = affiliate_links or []

        # Filter to only digital/software entities
        software_entities = [
            e for e in entities
            if isinstance(e, dict)
            and len(e.get("name", "").strip()) >= 3
            and self._is_digital_or_non_physical(e, category)
        ]

        for entity in software_entities:
            entity_name = entity.get("name", "").strip()
            if not entity_name:
                continue

            name_lower = entity_name.lower().strip()

            # Step 1: Check curated mapping
            url = self.KNOWN_SOFTWARE_URLS.get(name_lower)

            # Step 2: Check backend affiliate links for a matching pattern
            if not url and affiliate_links:
                for mapping in affiliate_links:
                    pattern = mapping.get("pattern", "").lower()
                    if pattern and pattern in name_lower:
                        url = mapping.get("url")
                        break

            # Step 3: If no URL found, skip this entity (don't guess)
            if not url:
                continue

            content = self._wrap_entity_in_link(content, entity_name, url)

        return content

    def inject_product_cards(self, content: str, entities: list, product_images: dict = None, category: str = "") -> str:
        """Inject styled visual product highlight cards under top product H3 sections."""
        if not entities:
            return content

        product_images = product_images or {}
        product_entities = [
            e for e in entities
            if isinstance(e, dict)
            and len(e.get("name", "").strip()) >= 3
            and not self._is_digital_or_non_physical(e, category)
        ]

        if not product_entities:
            return content

        lines = content.split('\n')
        new_lines = []
        card_count = 0
        used_images = set()

        for line in lines:
            new_lines.append(line)
            stripped = line.strip()

            # Detect H3 product headings like "### 1. Apple Watch SE" or "### Garmin Forerunner 245"
            if stripped.startswith('###'):
                matched_product = None
                for pe in product_entities:
                    pname = pe["name"]
                    if pname.lower() in stripped.lower():
                        matched_product = pname
                        break

                if matched_product:
                    if card_count == 0:
                        badge = "Top Pick"
                        sub_badge = "⭐ Editor's Choice"
                    elif card_count == 1:
                        badge = "Best Value"
                        sub_badge = "⚡ Great Value"
                    else:
                        badge = "Recommended"
                        sub_badge = "✓ Verified Pick"

                    img_url = product_images.get(matched_product, "")
                    if img_url in used_images:
                        img_url = ""
                    elif img_url:
                        used_images.add(img_url)

                    card_html = self._render_product_card(
                        product_name=matched_product,
                        badge=badge,
                        sub_badge=sub_badge,
                        image_url=img_url,
                        affiliate_tag=self.affiliate_tag
                    )
                    new_lines.append("")
                    new_lines.append(card_html)
                    new_lines.append("")
                    card_count += 1

        return '\n'.join(new_lines)

    def _render_product_card(self, product_name: str, badge: str, sub_badge: str = "⭐ Editor's Choice", image_url: str = "", affiliate_tag: str = "") -> str:
        """Generate a self-contained, responsive HTML product showcase card."""
        encoded = quote_plus(product_name)
        amazon_url = f"https://www.amazon.com/s?k={encoded}"
        if affiliate_tag:
            amazon_url += f"&tag={affiliate_tag}"

        image_html = ""
        if image_url:
            image_html = f'''
  <div style="flex: 0 0 140px; max-width: 160px; margin: 0 auto; text-align: center;">
    <img src="{image_url}" alt="{product_name}" loading="lazy" style="max-width: 100%; max-height: 140px; object-fit: contain; border-radius: 8px;" />
  </div>'''

        badge_bg = "#eff6ff" if badge == "Top Pick" else ("#fef3c7" if badge == "Best Value" else "#f0fdf4")
        badge_color = "#1d4ed8" if badge == "Top Pick" else ("#b45309" if badge == "Best Value" else "#15803d")

        card = f'''<div class="product-highlight-card" style="border: 1px solid #e2e8f0; border-radius: 16px; padding: 18px 22px; margin: 20px 0; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.04); display: flex; flex-direction: row; flex-wrap: wrap; gap: 20px; align-items: center;">{image_html}
  <div style="flex: 1; min-width: 240px;">
    <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
      <span style="background-color: {badge_bg}; color: {badge_color}; font-size: 0.75rem; font-weight: 700; padding: 3px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em;">{badge}</span>
      <span style="color: #64748b; font-weight: 600; font-size: 0.8rem;">{sub_badge}</span>
    </div>
    <div style="margin-top: 10px;">
      <a href="{amazon_url}" target="_blank" rel="nofollow sponsored noopener" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-weight: 600; padding: 9px 20px; border-radius: 8px; text-decoration: none; font-size: 0.875rem; transition: background-color 0.2s;">Check Price on Amazon &rarr;</a>
    </div>
  </div>
</div>'''
        return card

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _remove_dashes(content: str) -> str:
        """Replace em dashes (—) and en dashes (–) with clean colons or spaced hyphens,
        and normalize horizontal whitespace without collapsing newlines.
        """
        # Replace dash following bold markers or list prefixes with colon (e.g., "**Feature** — description" -> "**Feature**: description")
        content = re.sub(r'(\*\*[^*]+\*\*)\s*[\u2014\u2013]\s*', r'\1: ', content)
        # Replace standalone em/en dashes inside sentences with spaced hyphens
        content = content.replace("\u2014", " - ")
        content = content.replace("\u2013", " - ")
        # Clean up horizontal double spaces/tabs on lines only (preserving newlines for Markdown paragraphs)
        content = re.sub(r'[^\S\r\n]{2,}', ' ', content)
        return content

    @staticmethod
    def _fix_bold_headings(content: str) -> str:
        """Convert standalone bold-only lines into ## headings and strip bold markers from existing headings of any level."""
        content = re.sub(r'^(\s*#+)\s*[\*_]{1,2}([^*_]+)[\*_]{1,2}\s*$', r'\1 \2', content, flags=re.MULTILINE)
        pattern = re.compile(r'^(\s*)\*\*([^*]+)\*\*\s*$', re.MULTILINE)
        return pattern.sub(r'## \2', content)

    @staticmethod
    def _strip_markdown_markers_from_headings(content: str) -> str:
        """Strip bold and italic markers from any Markdown heading line."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#'):
                match = re.match(r'^(\s*#+)\s*(.*)', line)
                if match:
                    prefix = match.group(1)
                    text = match.group(2)
                    prev = None
                    while text != prev:
                        prev = text
                        text = re.sub(r'^[\*_]{1,3}(.+?)[\*_]{1,3}$', r'\1', text.strip())
                    text = text.replace('**', '').replace('__', '')
                    text = text.replace('*', '').replace('_', '')
                    lines[i] = f"{prefix} {text.strip()}"
        return '\n'.join(lines)

    @staticmethod
    def _split_inlined_lists(content: str) -> str:
        """Split inline checklists into formatted bullet lists."""
        lines = content.split('\n')
        result = []
        in_code_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue

            if in_code_block or stripped.startswith('#') or '|' in stripped:
                result.append(line)
                continue

            if '✅' in stripped or '❌' in stripped:
                indices = [stripped.find('✅'), stripped.find('❌')]
                valid_indices = [idx for idx in indices if idx != -1]
                if not valid_indices:
                    result.append(line)
                    continue
                first_idx = min(valid_indices)
                prefix = stripped[:first_idx].strip()
                emoji_part = stripped[first_idx:]
                parts = re.findall(r'([✅❌])\s*([^✅❌]+)', emoji_part)
                if len(parts) > 1:
                    bullet_lines = []
                    if prefix and prefix not in ["-", "*"]:
                        bullet_lines.append(prefix)
                    for emoji, text in parts:
                        bullet_lines.append(f"- {emoji} {text.strip()}")
                    result.append('\n'.join(bullet_lines))
                    continue
            result.append(line)
        return '\n'.join(result)

    @staticmethod
    def _unwrap_code_blocks(content: str) -> str:
        """Convert fenced code blocks into blockquotes for non-tutorial articles."""
        lines = content.split('\n')
        result: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                if stripped:
                    result.append(f"> {stripped}")
                else:
                    result.append(">")
            else:
                result.append(line)

        return '\n'.join(result)

    @staticmethod
    def _fix_heading_spacing(content: str) -> str:
        """Ensure a blank line exists before and after every heading."""
        lines = content.split('\n')
        result: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            is_heading = stripped.startswith('#')

            if is_heading:
                if result and result[-1].strip() != '':
                    result.append('')
                result.append(line)
            else:
                if result and result[-1].strip().startswith('#') and stripped != '':
                    result.append('')
                result.append(line)

        return '\n'.join(result)

    @staticmethod
    def _wrap_entity_in_link(content: str, entity_name: str, amazon_url: str) -> str:
        """Wrap the first valid body-text mention of entity_name in a Markdown link."""
        lines = content.split('\n')
        replaced = False
        result: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue

            if replaced or in_code_block:
                result.append(line)
                continue

            # Skip headings, empty lines, and lines that already have amazon links
            if stripped.startswith('#') or not stripped or 'amazon.com' in line.lower():
                result.append(line)
                continue

            pattern = re.compile(rf'\b({re.escape(entity_name)})\b', re.IGNORECASE)
            match = pattern.search(line)
            if not match:
                result.append(line)
                continue

            idx = match.start(1)
            end_idx = match.end(1)

            # Don't wrap if already inside an existing Markdown link
            before = line[:idx]
            if '[' in before:
                bracket_pos = before.rfind('[')
                between = before[bracket_pos:]
                if '](' not in between and ')' not in between:
                    result.append(line)
                    continue

            actual_name_in_text = match.group(1)
            link_md = f"[{actual_name_in_text}]({amazon_url})"

            line = line[:idx] + link_md + line[end_idx:]
            replaced = True
            result.append(line)

        return '\n'.join(result)

    def _append_affiliate_tag(self, content: str) -> str:
        """Append the affiliate tag to existing Amazon links that lack one."""
        tag = self.affiliate_tag

        def _add_tag(match: re.Match) -> str:
            url = match.group(1)
            if f"tag={tag}" in url:
                return url
            if "tag=" in url:
                return url
            return f"{url}&tag={tag}"

        return re.sub(
            r'(https://www\.amazon\.com/s\?k=[^)\s]+)',
            _add_tag,
            content,
        )
