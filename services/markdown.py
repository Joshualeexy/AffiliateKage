import markdown
import re


def to_html(markdown_text: str) -> str:
    """
    Convert Markdown text to HTML with table and fenced code extensions.

    Args:
        markdown_text (str): The Markdown text to convert

    Returns:
        str: The converted HTML string
    """
    html = markdown.markdown(
        markdown_text,
        extensions=['tables', 'fenced_code']
    )

    # -- Step 1: Inject inline styles on headings -------------------------
    # The frontend editor strips heading styles, so we bake them in.
    # Use a negative lookahead to avoid adding a second style attribute if
    # one is already present (idempotent on re-runs).

    _HEADING_STYLES = {
        "h2": "font-size: 1.75em; margin-top: 1.5em; margin-bottom: 0.75em;",
        "h3": "font-size: 1.5em; margin-top: 1.25em; margin-bottom: 0.5em;",
        "h4": "font-size: 1.25em; margin-top: 1em; margin-bottom: 0.5em;",
    }

    for tag, style in _HEADING_STYLES.items():
        # Match opening tags that do NOT already have a style attribute
        html = re.sub(
            rf'<{tag}(?![^>]*style=)([^>]*)>',
            rf'<{tag}\1 style="{style}">',
            html,
            flags=re.IGNORECASE,
        )

    # -- Step 2: Strip <strong>/<em>/<b>/<i> from inside ALL headings -----
    # This runs AFTER style injection so nothing can re-introduce them.
    # We loop until stable to catch deeply nested cases.

    _INLINE_TAG_RE = re.compile(r'</?(?:strong|b|em|i)(?:\s[^>]*)?>', re.IGNORECASE)

    def _clean_heading(match: re.Match) -> str:
        open_tag = match.group(1)
        inner = match.group(2)
        close_tag = match.group(3)
        # Iteratively strip until no more inline tags remain
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

    return html