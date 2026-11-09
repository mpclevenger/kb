"""Guides, read from the Markdown files in content/guides/.

Each file is one guide: a short header between two --- lines, then the text in Markdown.
`manage.py sync_guides` turns them into drafts (or updates) for Tech Risk to review and publish.
See content/README.md.
"""

import hashlib
import re
from html import escape
from dataclasses import dataclass
from pathlib import Path

import markdown
from django.conf import settings
from django.utils.text import slugify

from apps.wiki.models import Section
from apps.wiki.richtext import clean_html

OWNER_ROLE = "Tech Risk"
GUIDES_DIR = Path(settings.BASE_DIR) / "content" / "guides"
FIELDS = {"title", "section", "platform", "order"}
LAST = 10_000  # guides without an order load after the numbered ones


class GuideFileError(Exception):
    """A guide file that cannot be read; the message names the file and says what to fix."""


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    section: str
    platform: str | None
    order: int
    body: str  # sanitized HTML
    file: str  # file name, for messages
    source_hash: str  # SHA-256 of the file's text, to tell whether the file changed


MERMAID_BLOCK = re.compile(r"^```mermaid[ \t]*\n(.*?)\n```[ \t]*$", re.S | re.M)


def markdown_to_html(body):
    """Markdown to HTML. A ```mermaid block becomes <pre class="mermaid"> holding the escaped diagram text."""
    diagrams = []

    def hold(match):
        diagrams.append(escape(match.group(1).strip("\n"), quote=False))
        return f"\n\nMERMAIDBLOCK{len(diagrams) - 1}X\n\n"

    html = markdown.markdown(MERMAID_BLOCK.sub(hold, body), extensions=["tables"])
    for number, text in enumerate(diagrams):
        html = html.replace(f"<p>MERMAIDBLOCK{number}X</p>", f'<pre class="mermaid">{text}</pre>')
    return html


def split_front_matter(text, name):
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise GuideFileError(f"{name}: the file must start with a line of three dashes (---) followed by title and section.")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise GuideFileError(f"{name}: the header at the top has no closing line of three dashes (---).") from None
    fields = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not colon or not key:
            raise GuideFileError(f"{name}: the header line '{line.strip()}' should look like 'title: Your title'.")
        if key not in FIELDS:
            raise GuideFileError(f"{name}: unknown header '{key}'. Allowed: {', '.join(sorted(FIELDS))}.")
        fields[key] = value
    return fields, "\n".join(lines[end + 1:])


def parse_guide(path):
    """Read one guide file into a Guide, or raise GuideFileError saying what is wrong."""
    path = Path(path)
    name = path.name
    text = path.read_text(encoding="utf-8")
    fields, body = split_front_matter(text, name)
    if path.stem != slugify(path.stem):
        raise GuideFileError(f"{name}: the file name must be lowercase words joined by dashes, like 'initiative-lifecycle.md'.")
    for required in ("title", "section"):
        if not fields.get(required):
            raise GuideFileError(f"{name}: the header needs a '{required}:' line.")
    if fields["section"] not in Section.values:
        raise GuideFileError(f"{name}: unknown section '{fields['section']}'. Use one of: {', '.join(Section.values)}.")
    try:
        order = int(fields["order"]) if fields.get("order") else LAST
    except ValueError:
        raise GuideFileError(f"{name}: 'order' must be a whole number, not '{fields['order']}'.") from None
    if not body.strip():
        raise GuideFileError(f"{name}: the guide has no text after the header.")
    html = markdown_to_html(body)
    html = clean_html(re.sub(r">\s*\n\s*<", "><", html))  # Markdown puts line breaks between tags; the editor does not
    return Guide(path.stem, fields["title"], fields["section"], fields.get("platform") or None, order, html,
                 name, hashlib.sha256(text.encode("utf-8")).hexdigest())


def load_guides(directory=GUIDES_DIR):
    """Every guide in the folder, in the order set by their 'order' lines (then by title)."""
    guides = [parse_guide(path) for path in sorted(Path(directory).glob("*.md"))]
    return sorted(guides, key=lambda guide: (guide.order, guide.title))
