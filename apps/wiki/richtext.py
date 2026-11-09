"""Cleans pasted text so only safe formatting is kept, and adds the links and cards for guide headings."""

import re
from html import unescape
from html.parser import HTMLParser

import nh3
from django import forms
from django.utils.text import slugify

from .widgets import RichTextWidget

ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "h4", "strong", "em", "ul", "ol", "li", "a",
    "blockquote", "code", "pre", "hr", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href"},
    "pre": {"class"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}
ALLOWED_SCHEMES = {"http", "https", "mailto"}
CLEAN_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "template", "noscript", "title", "head"}

NBSP = "\u00a0"
_NBSP_RUN = re.compile(r"(?:&nbsp;|&#160;|&#xa0;|\u00a0)(?:\s*(?:&nbsp;|&#160;|&#xa0;|\u00a0))+", re.I)
_NBSP_ONLY = r"(?:\s|&nbsp;|&#160;|&#xa0;|\u00a0)*"
_EMPTY_PARAGRAPH = re.compile(
    r"<p(?:\s[^>]*)?>" + _NBSP_ONLY + r"(?:<br\s*/?>" + _NBSP_ONLY + r")*</p>", re.I
)
# Word and Google Docs paste b, i and h1; we store strong, em and h2. After nh3 the tags carry no
# attributes, so a plain text replace is enough.
_TAG_RENAMES = {"<b>": "<strong>", "</b>": "</strong>", "<i>": "<em>", "</i>": "</em>", "<h1>": "<h2>", "</h1>": "</h2>"}

# One Word list paragraph. The tag part stops at the next "<" and the body stops at "</p>", the
# next "<p" or the end, so a missing close tag cannot make the regex rescan the rest of the text.
_WORD_LIST_ITEM = re.compile(
    r"<p(?=[^<>]*(?:MsoListParagraph|mso-list))[^<>]*>(.*?)(?:</p>|(?=<p[\s>])|\Z)", re.S | re.I
)
_WORD_LIST_RUN = re.compile(f"(?:{_WORD_LIST_ITEM.pattern}\\s*)+", re.S | re.I)
_WORD_MARKER = re.compile(
    r"^\s*(?:<span[^>]*mso-list:\s*Ignore[^>]*>.*?</span>|<span[^>]*>\s*(?:&middot;|&bull;|&sect;|[\u00b7\u2022\u00a7\u25aa\uf0b7\uf0a7o]|\d+[.)]|[a-zA-Z][.)])(?:&nbsp;|\s|\u00a0)*</span>|(?:[\u00b7\u2022\u00a7\u25aa\uf0b7\uf0a7]|&middot;|&bull;)(?:&nbsp;|\s|\u00a0)*|(?:\d+|[a-zA-Z])[.)](?:&nbsp;|\s|\u00a0)+)",
    re.S | re.I,
)
_ORDERED_MARKER = re.compile(r"^\s*(?:<span[^>]*>\s*)?(?:\d+|[a-zA-Z])[.)]", re.I)


def _convert_word_lists(html):
    """Turn runs of Word list paragraphs into <ul>/<ol>; nh3 would only flatten them to <p>."""

    def convert_run(match):
        items = _WORD_LIST_ITEM.findall(match.group(0))
        ordered = bool(_ORDERED_MARKER.match(items[0]))
        body = "".join(f"<li>{_WORD_MARKER.sub('', item.strip(), count=1).strip()}</li>" for item in items)
        tag = "ol" if ordered else "ul"
        return f"<{tag}>{body}</{tag}>"

    return _WORD_LIST_RUN.sub(convert_run, html)


def _drop_offsite_relative_url(url):
    """nh3 keeps relative links; refuse "//host/path", which a browser treats as another site."""
    return None if url.startswith("//") else url


def _only_mermaid_class(tag, attribute, value):
    """The one class the site allows: a diagram block, <pre class="mermaid">."""
    if tag == "pre" and attribute == "class":
        return "mermaid" if value.strip() == "mermaid" else None
    return value


def clean_html(html):
    """Sanitize pasted or stored rich text down to the allowed tags (nh3 does the security work)."""
    if not html or not html.strip():
        return ""
    cleaned = nh3.clean(
        _convert_word_lists(html),
        tags=ALLOWED_TAGS | {"b", "i", "h1"},
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_only_mermaid_class,
        url_schemes=ALLOWED_SCHEMES,
        url_relative=_drop_offsite_relative_url,
        link_rel="noopener noreferrer",
        strip_comments=True,
        clean_content_tags=CLEAN_CONTENT_TAGS,
    )
    for old, new in _TAG_RENAMES.items():
        cleaned = cleaned.replace(old, new)
    cleaned = _NBSP_RUN.sub(" ", cleaned).replace(NBSP, " ")
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _EMPTY_PARAGRAPH.sub("", cleaned)
    return cleaned.strip()


def _format_attrs(attrs):
    parts = []
    for name, value in attrs:
        if value is None:
            parts.append(f" {name}")
        else:
            escaped = value.replace("&", "&amp;").replace('"', "&quot;")
            parts.append(f' {name}="{escaped}"')
    return "".join(parts)


# Short, stable links for numbered checklist items: a Heading 4 "Item 3 ..." under a Heading 2
# "Stage 1 ..." gets the id "stage-1-item-3". The initiative tracker links to these.
_STAGE = re.compile(r"^stage (\d+)\b", re.I)
_ITEM = re.compile(r"^item (\d+)\b", re.I)


class _AnchorParser(HTMLParser):
    """Copies the document unchanged, except headings get an id.

    h2 and h3 get an id from their text and are collected in `toc`. h4 gets an id too but stays
    out of the table of contents.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []  # finished HTML pieces
        self.toc = []
        self._used_ids = set()
        self._heading = None  # the heading being read: {"tag", "attrs", "html", "text"}
        self._stage = None  # number from the latest "Stage N" h2, if any

    def _id_for(self, tag, text):
        if tag == "h2":
            stage = _STAGE.match(text)
            self._stage = stage.group(1) if stage else None
        item = _ITEM.match(text)
        if tag == "h4" and item and self._stage is not None:
            return self._unique_id(f"stage-{self._stage}-item-{item.group(1)}")
        return self._unique_id(text)

    def _unique_id(self, text):
        base = slugify(text) or "section"
        slug, n = base, 2
        while slug in self._used_ids:
            slug = f"{base}-{n}"
            n += 1
        self._used_ids.add(slug)
        return slug

    def _write(self, html, text=""):
        """Add `html` to the output; `text` is its plain-text form, used for heading titles."""
        if self._heading:
            self._heading["html"].append(html)
            self._heading["text"].append(text)
        else:
            self.out.append(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3", "h4") and not self._heading:
            self._heading = {"tag": tag, "attrs": [a for a in attrs if a[0] != "id"], "html": [], "text": []}
        else:
            self._write(f"<{tag}{_format_attrs(attrs)}>")

    def handle_startendtag(self, tag, attrs):
        self._write(f"<{tag}{_format_attrs(attrs)}>")

    def handle_endtag(self, tag):
        heading = self._heading
        if not heading or tag != heading["tag"]:
            self._write(f"</{tag}>")
            return
        self._heading = None
        text = re.sub(r"\s+", " ", "".join(heading["text"])).strip()
        slug = self._id_for(tag, text)
        attrs = _format_attrs(heading["attrs"] + [("id", slug)])
        self.out.append(f"<{tag}{attrs}>{''.join(heading['html'])}</{tag}>")
        if tag != "h4":
            self.toc.append({"level": int(tag[1]), "id": slug, "text": text})

    def handle_data(self, data):
        self._write(data, data)

    def handle_entityref(self, name):
        self._write(f"&{name};", unescape(f"&{name};"))

    def handle_charref(self, name):
        self._write(f"&#{name};", unescape(f"&#{name};"))

    def handle_comment(self, data):
        self._write(f"<!--{data}-->")


def add_heading_anchors(html):
    """Give every h2, h3 and h4 an id. Returns (html, table of contents of the h2s and h3s).

    Only call this on HTML that has already gone through clean_html: it rebuilds
    the markup but does not sanitize it.
    """
    if not html:
        return "", []
    parser = _AnchorParser()
    parser.feed(html)
    parser.close()
    return "".join(parser.out), parser.toc


_H2 = re.compile(r'<h2 id="([^"]+)">(.*?)</h2>', re.S)


def split_sections(html):
    """Split anchored HTML (from add_heading_anchors) at each h2.

    Returns (intro, sections): intro is the HTML before the first h2, and each section is
    {"id", "title", "html"} with the h2 itself left out, so the page can show it as a card.
    """
    parts = _H2.split(html or "")
    intro, rest = parts[0], parts[1:]
    sections = []
    for i in range(0, len(rest), 3):
        anchor, title, body = rest[i:i + 3]
        sections.append({"id": anchor, "title": unescape(re.sub(r"<[^>]+>", "", title)).strip(), "html": body})
    return intro, sections


MAX_BODY_LENGTH = 200_000  # characters of pasted HTML; far above any real page, stops runaway pastes


class RichTextField(forms.CharField):
    """Rich text input, cleaned on save.

    Readers clean the stored body again when they show it (see views_read.page).
    That is deliberate: seeds and code that write straight to the database skip this form.
    """

    widget = RichTextWidget

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", MAX_BODY_LENGTH)
        kwargs.setdefault(
            "error_messages",
            {"max_length": "This is too long (%(show_value)d characters; the limit is %(limit_value)d). Split it into two pages."},
        )
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        return clean_html(value)
