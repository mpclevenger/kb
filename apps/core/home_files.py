"""The front page: what Tech Risk offers and a card for each of its tools. The text lives in content/home/.

`content/home/index.md` holds the page title and the short pitch. Each file in `content/home/tools/` is one
card, with a page of its own for the details. A card's button goes to a page in TRAC (`link: /guides/`) or to
another app whose address is set on the platform (`link: env TRUST_URL`). `under_construction: yes` marks a
tool that is a demo to try and give feedback on; `coming_soon: yes` marks one that isn't available yet (its button is
turned off even if its address is set); `also_label` and `also_link` add a second link to the card. Nothing here is stored in the
database, so a change to these files shows once the site restarts with them.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify

from apps.wiki.richtext import clean_html
from apps.wiki.starter_guides import markdown_to_html

FOLDER = Path(settings.BASE_DIR) / "content" / "home"
PAGE_FIELDS = {"title"}
TOOL_FIELDS = {"title", "summary", "link", "button", "order", "under_construction", "coming_soon", "also_label", "also_link"}


class HomeFileError(ValueError):
    pass


@dataclass
class Tool:
    slug: str
    title: str
    summary: str
    button: str
    url: str  # empty when the app's address isn't set yet
    external: bool
    order: int
    html: str
    under_construction: bool = False  # a demo to try and give feedback on, not officially launched
    coming_soon: bool = False  # not available yet: the card says so and its button is off
    also_label: str = ""  # an optional second link on the card, for example a request form
    also_url: str = ""


@dataclass
class Page:
    title: str
    html: str


def _read(path, allowed, required):
    """Front matter and Markdown body of one file, or HomeFileError saying what is wrong."""
    lines = path.read_text(encoding="utf-8").lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise HomeFileError(f"{path.name}: the file must start with a line of three dashes (---).")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise HomeFileError(f"{path.name}: the header has no closing line of three dashes (---).") from None
    fields = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        key = key.strip().lower()
        if not colon or key not in allowed:
            raise HomeFileError(f"{path.name}: '{line.strip()}' isn't a known header line. Use: {', '.join(sorted(allowed))}.")
        fields[key] = value.strip()
    for key in required:
        if not fields.get(key):
            raise HomeFileError(f"{path.name}: the header needs a '{key}' line.")
    html = clean_html(markdown_to_html("\n".join(lines[end + 1:])))
    return fields, html


def _url(link, name):
    """(address, is another app) for a link line."""
    if link.startswith("env "):
        variable = link[4:].strip()
        if not variable.isidentifier():
            raise HomeFileError(f"{name}: 'link: env ...' needs the name of a setting, like 'link: env TRUST_URL'.")
        return os.environ.get(variable, "").strip(), True
    if link.startswith("/") and not link.startswith("//"):
        return link, False
    if link.startswith("https://"):
        return link, True
    raise HomeFileError(f"{name}: the link must be a TRAC page (/guides/), an https:// address, or 'env SETTING_NAME'.")


def landing(folder=None):
    folder = Path(folder or FOLDER)
    fields, html = _read(folder / "index.md", PAGE_FIELDS, ("title",))
    return Page(title=fields["title"], html=html)


def tools(folder=None):
    folder = Path(folder or FOLDER) / "tools"
    found = []
    for path in sorted(folder.glob("*.md")):
        if path.stem != slugify(path.stem):
            raise HomeFileError(f"{path.name}: the file name must be lowercase words joined by dashes.")
        fields, html = _read(path, TOOL_FIELDS, ("title", "summary", "link", "button"))
        url, external = _url(fields["link"], path.name)
        try:
            order = int(fields.get("order") or 99)
        except ValueError:
            raise HomeFileError(f"{path.name}: 'order' must be a whole number.") from None
        flags = {}
        for name in ("under_construction", "coming_soon"):
            flags[name] = fields.get(name, "no").lower()
            if flags[name] not in ("yes", "no"):
                raise HomeFileError(f"{path.name}: '{name}' must be yes or no.")
        also_label, also_url = fields.get("also_label", ""), ""
        if bool(also_label) != bool(fields.get("also_link")):
            raise HomeFileError(f"{path.name}: 'also_label' and 'also_link' go together; give both or neither.")
        if also_label:
            also_url, _ = _url(fields["also_link"], path.name)
        found.append(Tool(
            path.stem, fields["title"], fields["summary"], fields["button"], url, external, order, html,
            under_construction=flags["under_construction"] == "yes", coming_soon=flags["coming_soon"] == "yes",
            also_label=also_label, also_url=also_url,
        ))
    return sorted(found, key=lambda tool: (tool.order, tool.title))


def problems(folder=None):
    """Plain-word problems with the home page files, for check_content."""
    try:
        landing(folder)
        tools(folder)
    except (HomeFileError, OSError) as error:
        return [str(error)]
    return []
