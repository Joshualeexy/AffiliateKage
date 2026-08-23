import markdown
import re


def to_html(markdown_text: str, include_disclosure: bool = True) -> str:
    """
    Convert Markdown text to HTML with table, fenced code extensions,
    FTC affiliate disclosure, and SEO/monetization compliance attributes.

    Args:
        markdown_text (str): The Markdown text to convert
        include_disclosure (bool): Whether to prepend the FTC affiliate disclosure

    Returns:
        str: The converted HTML string
    """
    html = markdown.markdown(
        markdown_text,
        extensions=['tables', 'fenced_code']
    )

    # -- Step 1: Prepend FTC Affiliate Disclosure -------------------------
    if include_disclosure and "Affiliate Disclosure:" not in html:
        disclosure_html = (
            '<div class="affiliate-disclosure" style="background-color: #f8fafc; '
            'border-left: 4px solid #3b82f6; padding: 12px 16px; margin-bottom: 24px; '
            'font-size: 0.875rem; color: #475569; border-radius: 4px; line-height: 1.5;">'
            '<strong>Affiliate Disclosure:</strong> As an Amazon Associate and affiliate partner, '
            'we may earn commissions from qualifying purchases made through links on this page at no extra cost to you.'
            '</div>\n'
        )
        html = disclosure_html + html

    # -- Step 2: Inject inline styles on headings -------------------------
    _HEADING_STYLES = {
        "h2": "font-size: 1.75em; margin-top: 1.5em; margin-bottom: 0.75em;",
        "h3": "font-size: 1.5em; margin-top: 1.25em; margin-bottom: 0.5em;",
        "h4": "font-size: 1.25em; margin-top: 1em; margin-bottom: 0.5em;",
    }

    for tag, style in _HEADING_STYLES.items():
        html = re.sub(
            rf'<{tag}(?![^>]*style=)([^>]*)>',
            rf'<{tag}\1 style="{style}">',
            html,
            flags=re.IGNORECASE,
        )

    # -- Step 3: Strip <strong>/<em>/<b>/<i> from inside ALL headings -----
    _INLINE_TAG_RE = re.compile(r'</?(?:strong|b|em|i)(?:\s[^>]*)?>', re.IGNORECASE)

    def _clean_heading(match: re.Match) -> str:
        open_tag = match.group(1)
        inner = match.group(2)
        close_tag = match.group(3)
        prev = None
        while inner != prev:
            prev = inner
            inner = _INLINE_TAG_RE.sub('', inner)
        return f"{open_tag}{inner.strip()}{close_tag}"

    html = re.sub(
        r'(<h[1-6]\b[^>]*>)(.*?)(</h[1-6]>)',
        _clean_heading,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # -- Step 4: Add rel="nofollow sponsored noopener" & target="_blank" to external links ---
    def _modify_link(match: re.Match) -> str:
        attrs = match.group(1)
        href_match = re.search(r'href=[\"\']([^\"\']+)[\"\']', attrs, re.IGNORECASE)
        if not href_match:
            return match.group(0)
        href = href_match.group(1).lower()

        # Keep internal blog links clean
        if 'ejiroinspire.com' in href or href.startswith('/') or href.startswith('#'):
            return match.group(0)

        # External / Affiliate link: apply nofollow sponsored and target="_blank"
        attrs_clean = re.sub(r'\s*(rel|target)=[\"\'][^\"\']*[\"\']', '', attrs, flags=re.IGNORECASE)
        return f'<a{attrs_clean} target="_blank" rel="nofollow sponsored noopener">'

    html = re.sub(r'<a\b([^>]*)>', _modify_link, html, flags=re.IGNORECASE)

    # -- Step 5: Style Comparison Tables for clean display ----------------
    html = re.sub(
        r'<table(?![^>]*style=)([^>]*)>',
        r'<table\1 style="width: 100%; border-collapse: collapse; margin: 1.5em 0; font-size: 0.95em;">',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<th(?![^>]*style=)([^>]*)>',
        r'<th\1 style="border: 1px solid #cbd5e1; padding: 10px 14px; background-color: #f1f5f9; text-align: left;">',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<td(?![^>]*style=)([^>]*)>',
        r'<td\1 style="border: 1px solid #e2e8f0; padding: 10px 14px; text-align: left;">',
        html,
        flags=re.IGNORECASE,
    )

    return html