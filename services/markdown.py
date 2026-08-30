import markdown
import re


# -- Disclosure Templates --------------------------------------------------

AMAZON_DISCLOSURE = (
    '<div class="affiliate-disclosure" style="background-color: #f8fafc; '
    'border-left: 4px solid #3b82f6; padding: 12px 16px; margin-bottom: 24px; '
    'font-size: 0.875rem; color: #475569; border-radius: 4px; line-height: 1.5;">'
    '<strong>Affiliate Disclosure:</strong> As an Amazon Associate and affiliate partner, '
    'we may earn commissions from qualifying purchases made through links on this page at no extra cost to you.'
    '</div>\n'
)

GENERAL_AFFILIATE_DISCLOSURE = (
    '<div class="affiliate-disclosure" style="background-color: #f8fafc; '
    'border-left: 4px solid #8b5cf6; padding: 12px 16px; margin-bottom: 24px; '
    'font-size: 0.875rem; color: #475569; border-radius: 4px; line-height: 1.5;">'
    '<strong>Disclosure:</strong> Some links on this page are affiliate links. '
    'We may earn a commission if you sign up through our links, at no extra cost to you. '
    'This helps support our editorial work.'
    '</div>\n'
)


def _detect_disclosure_type(html: str) -> str | None:
    """Determine which disclosure to show based on the links present in the HTML.
    
    Returns:
        'amazon' if Amazon product links are present.
        'general' if other external affiliate-style links are present.
        None if no affiliate links detected.
    """
    if 'amazon.com' in html.lower():
        return 'amazon'
    
    # Check for common affiliate / SaaS referral patterns
    affiliate_indicators = [
        'ref=', 'tag=', 'affiliate', 'partner', 'referral',
        'shareasale', 'commission', 'awin', 'cj.com', 'impact.com',
    ]
    lower_html = html.lower()
    for indicator in affiliate_indicators:
        if indicator in lower_html:
            return 'general'
    
    # Check for external links with rel="nofollow sponsored"
    if 'rel="nofollow sponsored' in lower_html:
        return 'general'
    
    return None


def to_html(markdown_text: str, include_disclosure: bool = True) -> str:
    """
    Convert Markdown text to HTML with table, fenced code extensions,
    context-aware affiliate disclosure, and SEO/monetization compliance attributes.

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

    # -- Step 1: Context-Aware Affiliate Disclosure -----------------------
    if include_disclosure and "Affiliate Disclosure:" not in html and "Disclosure:" not in html:
        disclosure_type = _detect_disclosure_type(html)
        if disclosure_type == 'amazon':
            html = AMAZON_DISCLOSURE + html
        elif disclosure_type == 'general':
            html = GENERAL_AFFILIATE_DISCLOSURE + html
        # If None, omit disclosure entirely (pure informational article)

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
        attrs_clean = re.sub(r'\s*(rel|target)=[\"\'][^\"\']*[\"\']\s*', ' ', attrs, flags=re.IGNORECASE).strip()
        if attrs_clean:
            return f'<a {attrs_clean} target="_blank" rel="nofollow sponsored noopener">'
        return '<a target="_blank" rel="nofollow sponsored noopener">'

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

    # -- Step 6: Style YouTube embeds for responsive display ---------------
    def _wrap_youtube_iframe(m: re.Match) -> str:
        attrs = m.group(1)
        content = m.group(2)
        return (
            f'<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 24px 0; border-radius: 12px;">'
            f'<iframe{attrs} style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; border-radius: 12px;" allowfullscreen>{content}</iframe>'
            f'</div>'
        )

    html = re.sub(
        r'<iframe([^>]*(?:youtube|youtube-nocookie)[^>]*)>(.*?)</iframe>',
        _wrap_youtube_iframe,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return html