"""Markdown rendering for knowledge base articles.

Articles are written by an organization's team but shown to anyone on its
public help center, so a body must not be able to inject markup: the
"js-default" preset escapes raw HTML, and markdown-it refuses javascript:,
vbscript: and data: link targets. The rendered HTML is therefore safe to
insert into a page as-is.
"""

import html
import re

from markdown_it import MarkdownIt

_renderer = MarkdownIt("js-default")
_TAGS = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def render_markdown(source: str) -> str:
    return _renderer.render(source)


def plain_excerpt(source: str, max_length: int = 180) -> str:
    """The article's opening text without formatting, cut at a word boundary."""
    rendered = _TAGS.sub(" ", render_markdown(source))
    text = _WHITESPACE.sub(" ", html.unescape(rendered)).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rsplit(" ", 1)[0] + "…"
