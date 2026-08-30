#!/usr/bin/env python3
"""
Batch Post Remediation Script for ejiroinspire.com

Fetches published posts from the admin API, re-sanitizes their HTML content & titles,
and pushes the cleaned version back. Same slug, same URL — zero SEO disruption.

Features:
  1. Fixes collapsed headings swallowing paragraphs.
  2. Wraps orphaned text blocks in proper <p> tags.
  3. Eliminates double-boldness (<strong>/<b> inside <h1-6> headings).
  4. Removes broken/placeholder images (placehold.co, empty src).
  5. Fixes foreign currency leaks (₹, Rs., INR, ₦).
  6. Strips fake Amazon search links on software/apps and converts to clean text/homepages.
  7. Ensures compliant rel="nofollow sponsored noopener" and target="_blank" on external links.
  8. Removes inappropriate Amazon Associate disclosures from non-Amazon posts.
  9. Removes static Amazon prices violating Associates terms.
"""

import argparse
import os
import re
import sys
import time
from typing import Optional, Tuple, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import requests

API_URL = os.getenv("API_URL")
API_TOKEN = os.getenv("API_TOKEN")

if not API_URL or not API_TOKEN:
    print("ERROR: API_URL and API_TOKEN must be set in .env")
    sys.exit(1)


# ── Curated Software URL Dictionary ──────────────────────────────────────────

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
    "duolingo kids": "https://www.duolingo.com",
    "lingokids": "https://lingokids.com",
    "busuu": "https://www.busuu.com",
    "busuu for kids": "https://www.busuu.com",
    "khan academy": "https://www.khanacademy.org",
    "khan academy kids": "https://learn.khanacademy.org/khan-academy-kids",
    "lingualift": "https://www.lingualift.com",
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

DIGITAL_KEYWORDS = {
    "app", "software", "vpn", "hosting", "domain", "saas", "builder",
    "registrar", "bot", "cloud", "platform", "extension", "plugin",
}


# ── Sanitization Transformers ────────────────────────────────────────────────

def fix_heading_structure(html: str) -> str:
    """Split oversized headings (>200 chars) that swallowed paragraphs."""
    def _split_heading(match: re.Match) -> str:
        tag = match.group(1)
        attrs = match.group(2) or ""
        content = match.group(3)

        if len(content.strip()) < 180:
            return match.group(0)

        # Split at first sentence end after 20+ chars
        split_match = re.search(r'^(.{20,120}?[.!?])\s+(.+)$', content.strip(), re.DOTALL)
        if split_match:
            heading_text = split_match.group(1).strip()
            paragraph_text = split_match.group(2).strip()
            return f'<{tag}{attrs}>{heading_text}</{tag}>\n<p>{paragraph_text}</p>'

        return match.group(0)

    return re.sub(
        r'<(h[1-6])(\s[^>]*)?>(.+?)</(h[1-6])>',
        _split_heading,
        html,
        flags=re.IGNORECASE | re.DOTALL
    )


def fix_missing_paragraphs(html: str) -> str:
    """Wrap orphaned text blocks in <p> tags."""
    lines = html.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        if stripped.startswith('<') or stripped.startswith('-') or stripped.startswith('*'):
            result.append(line)
            continue

        result.append(f'<p>{stripped}</p>')

    return '\n'.join(result)


def fix_double_boldness(html: str) -> str:
    """Remove <strong> or <b> tags wrapping heading text."""
    # <hX><strong>Heading</strong></hX> -> <hX>Heading</hX>
    html = re.sub(
        r'(<h[1-6][^>]*>)\s*<(?:strong|b)\b[^>]*>(.*?)</(?:strong|b)>\s*(</h[1-6]>)',
        r'\1\2\3',
        html,
        flags=re.IGNORECASE
    )
    # Inline trailing bold markers in headings
    html = re.sub(
        r'(<h[1-6][^>]*>)\s*\*\*(.*?)\*\*\s*(</h[1-6]>)',
        r'\1\2\3',
        html,
        flags=re.IGNORECASE
    )
    return html


def fix_broken_images(html: str) -> str:
    """Remove placeholder or broken images and empty anchor wrappers."""
    # Remove placehold.co images and 1x1 data pixels
    html = re.sub(
        r'<img\b[^>]*src=["\'](?:https?://placehold\.co[^\s"\']*|data:image[^\s"\']*)["\'][^>]*>',
        '',
        html,
        flags=re.IGNORECASE
    )
    # Remove img tags with empty src
    html = re.sub(r'<img\b[^>]*src=["\']\s*["\'][^>]*>', '', html, flags=re.IGNORECASE)
    # Remove empty anchors created by removed images
    html = re.sub(r'<a\b[^>]*>\s*</a>', '', html, flags=re.IGNORECASE)
    return html


def fix_foreign_currency(text: str) -> str:
    """Normalize foreign currencies (₹, Rs., INR, ₦) to clean USD dollar signs."""
    text = re.sub(r'[₹]\s*([0-9,]+)', r'$\1', text)
    text = re.sub(r'\bRs\.?\s*([0-9,]+)', r'$\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\b([0-9,]+)\s*INR\b', r'$\1', text, flags=re.IGNORECASE)
    text = re.sub(r'[₦]\s*([0-9,]+)', r'$\1', text)
    text = re.sub(r'\bNGN\s*([0-9,]+)', r'$\1', text, flags=re.IGNORECASE)
    return text


def strip_software_amazon_links(html: str) -> str:
    """Strip Amazon search links from software/apps and replace with homepage or clean text."""
    def _clean_software_link(match: re.Match) -> str:
        attrs = match.group(1)
        anchor_text = match.group(2)
        lower_text = anchor_text.lower().strip()

        # Check if anchor is a known software or digital tool
        is_digital = (
            lower_text in KNOWN_SOFTWARE_URLS
            or any(kw in lower_text for kw in DIGITAL_KEYWORDS)
        )

        if is_digital:
            homepage = KNOWN_SOFTWARE_URLS.get(lower_text)
            if homepage:
                return f'<a href="{homepage}" target="_blank" rel="nofollow sponsored noopener">{anchor_text}</a>'
            return anchor_text

        return match.group(0)

    return re.sub(
        r'<a\b([^>]*href=["\']https?://(?:www\.)?amazon\.com/s\?k=[^"\']+["\'][^>]*)>(.*?)</a>',
        _clean_software_link,
        html,
        flags=re.IGNORECASE | re.DOTALL
    )


def fix_external_links(html: str) -> str:
    """Add rel="nofollow sponsored noopener" and target="_blank" to external links."""
    def _modify_link(match: re.Match) -> str:
        attrs = match.group(1)
        href_match = re.search(r'href=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        if not href_match:
            return match.group(0)
        href = href_match.group(1).lower()

        if "ejiroinspire.com" in href or href.startswith("/") or href.startswith("#"):
            return match.group(0)

        attrs_clean = re.sub(r'\s*(rel|target)=["\'][^"\']*["\']\s*', ' ', attrs, flags=re.IGNORECASE).strip()
        if attrs_clean:
            return f'<a {attrs_clean} target="_blank" rel="nofollow sponsored noopener">'
        return '<a target="_blank" rel="nofollow sponsored noopener">'

    return re.sub(r'<a\b([^>]*)>', _modify_link, html, flags=re.IGNORECASE)


def fix_disclosure(html: str) -> str:
    """Ensure disclosure matches link content (remove Amazon disclosure if no Amazon links)."""
    has_amazon = 'amazon.com' in html.lower() or 'amzn.to' in html.lower()

    if not has_amazon:
        # Strip Amazon disclosure banner if present
        html = re.sub(
            r'<div class="affiliate-disclosure"[^>]*>[\s\S]*?Amazon Associate[\s\S]*?</div>\s*',
            '',
            html,
            flags=re.IGNORECASE
        )

    return html


def remove_static_prices(html: str) -> str:
    """Remove hardcoded static price lines."""
    return re.sub(
        r'<p\s+style="[^"]*color:\s*#B12704[^"]*">\s*\$[\d,.]+\s*</p>',
        '',
        html,
        flags=re.IGNORECASE
    )


def sanitize_post(title: str, html: str) -> Tuple[str, str]:
    """Run all sanitizers on post title and HTML content."""
    clean_title = fix_foreign_currency(title)

    clean_html = html
    clean_html = fix_heading_structure(clean_html)
    clean_html = fix_missing_paragraphs(clean_html)
    clean_html = fix_double_boldness(clean_html)
    clean_html = fix_broken_images(clean_html)
    clean_html = fix_foreign_currency(clean_html)
    clean_html = strip_software_amazon_links(clean_html)
    clean_html = fix_external_links(clean_html)
    clean_html = remove_static_prices(clean_html)
    clean_html = fix_disclosure(clean_html)

    return clean_title, clean_html


# ── API Client ───────────────────────────────────────────────────────────────

class RemediationClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {API_TOKEN}",
            "Accept": "application/json",
        })
        self.base_url = API_URL.rstrip("/")

    def fetch_all_posts(self) -> List[Dict[str, Any]]:
        all_posts = []
        page = 1
        while True:
            url = f"{self.base_url}/posts?page={page}&per_page=50"
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                posts = data.get("data", [])
                if not posts:
                    break
                all_posts.extend(posts)
                last_page = data.get("meta", {}).get("last_page") or data.get("last_page")
                if last_page and page >= last_page:
                    break
                page += 1
                time.sleep(0.2)
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
        return all_posts

    def update_post(self, post_id: int, payload: dict) -> bool:
        url = f"{self.base_url}/posts/{post_id}"
        try:
            resp = self.session.put(url, json=payload, timeout=20)
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"Update failed for post {post_id}: {e}")
            return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch remediate blog posts.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of posts to update")
    parser.add_argument("--post-id", type=int, action="append", help="Target specific post ID(s)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    client = RemediationClient()

    if args.post_id:
        posts = []
        for pid in args.post_id:
            resp = client.session.get(f"{client.base_url}/posts/{pid}")
            if resp.status_code == 200:
                posts.append(resp.json().get("data", resp.json()))
    else:
        print("Fetching all posts from API...")
        posts = client.fetch_all_posts()

    print(f"Total posts scanned: {len(posts)}")

    to_update = []
    for p in posts:
        pid = p.get("id")
        orig_title = p.get("title", "")
        orig_content = p.get("content", "")
        if not orig_content:
            continue

        clean_title, clean_content = sanitize_post(orig_title, orig_content)

        payload = {}
        changes = []

        if clean_title != orig_title:
            payload["title"] = clean_title
            changes.append(f"Title: '{orig_title[:40]}' -> '{clean_title[:40]}'")

        if clean_content != orig_content:
            payload["content"] = clean_content
            changes.append("Content cleaned (headings, paragraphs, links, currencies, disclosures)")

        if payload:
            to_update.append((pid, orig_title, payload, changes))

    print(f"\nPosts needing remediation: {len(to_update)} / {len(posts)}")

    if args.dry_run:
        print("\n--- SAMPLE DRY-RUN CHANGES (First 10) ---")
        for pid, title, _, changes in to_update[:10]:
            print(f"[{pid}] {title[:60]}")
            for c in changes:
                print(f"  • {c}")
        print("\nDry-run complete. No changes were applied.")
        return

    if not to_update:
        print("All posts are clean! Nothing to do.")
        return

    if args.limit > 0:
        to_update = to_update[:args.limit]
        print(f"Limiting execution to first {len(to_update)} posts as requested.")

    if not args.yes:
        ans = input(f"\nProceed with updating {len(to_update)} posts? [y/N]: ")
        if ans.lower() not in ("y", "yes"):
            print("Aborted.")
            return

    print(f"\nPushing updates to {len(to_update)} posts...")
    success = 0
    fail = 0

    for i, (pid, title, payload, _) in enumerate(to_update, 1):
        print(f"[{i}/{len(to_update)}] Updating post {pid}: {title[:45]}...", end=" ")
        if client.update_post(pid, payload):
            print("✅")
            success += 1
        else:
            print("❌")
            fail += 1
        time.sleep(0.4)

    print(f"\n{'='*60}")
    print(f"REMEDIATION FINISHED")
    print(f"  Updated successfully: {success}")
    print(f"  Failed:               {fail}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
