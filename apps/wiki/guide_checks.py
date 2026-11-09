"""Plain-words checks for the guide files (`check_guides`); the wording check is shared with `check_controls` and `check_platforms`."""

import re
from html import unescape
from pathlib import Path

from apps.wiki.models import Section

HELP_LINE = "If you're unsure, Tech Risk can help."
BANNED_PHRASES = ("standard", "reach out", "tell tech risk", "agree it with tech risk", "route", "through tech risk", "agreed channel")
# The Oversight levels guide uses "Standard" as the name of a level, shared with the initiative tracker.
STANDARD_ALLOWED_IN = {"oversight-levels"}

# A vendor's own name for a product, setting or tier always wins over the wording rules above, so these
# phrases are removed (whole phrases, any capitals) before the text is checked. Add only terms the content uses.
PRODUCT_TERMS = (
    "standard access mode",  # Databricks compute access mode (formerly "shared")
)


def banned_phrases_in(text):
    """The banned phrases in the text, ignoring vendor product terms. Used for guides, controls and platform files."""
    lowered = re.sub(r"\s+", " ", text.lower())  # a YAML line break can split a phrase
    for term in PRODUCT_TERMS:
        lowered = re.sub(rf"\b{re.escape(term)}\b", " ", lowered)
    return [phrase for phrase in BANNED_PHRASES if phrase in lowered]


def file_wording_problems(paths):
    """Plain-language wording problems in content files (controls and platform YAML), named by file."""
    problems = []
    for path in paths:
        for phrase in banned_phrases_in(Path(path).read_text(encoding="utf-8")):
            problems.append(
                f'{Path(path).name}: the text contains "{phrase}". Reword it, or if it is a vendor\'s own term, '
                f"add it to PRODUCT_TERMS in apps/wiki/guide_checks.py.")
    return problems


# A link to a team's own document that does not exist yet: [text](#todo-<team>-<doc>).
PLACEHOLDER_LINK = re.compile(r"\[([^\]]+)\]\((#todo-[a-z0-9-]+)\)")


def find_placeholders(text):
    """The (link text, target) pairs of every #todo- placeholder link in the text."""
    return PLACEHOLDER_LINK.findall(text)


# The diagram kinds the site supports (README: Diagrams). Each block also needs a title and a description.
DIAGRAM_KINDS = ("flowchart", "graph", "sequenceDiagram", "stateDiagram-v2")
MERMAID_PRE = re.compile(r'<pre class="mermaid">(.*?)</pre>', re.S)


def diagram_problems(html):
    """Plain-language problems with the diagrams (```mermaid blocks) in a guide's HTML."""
    problems = []
    for number, block in enumerate(MERMAID_PRE.findall(html), start=1):
        lines = [line.strip() for line in unescape(block).splitlines() if line.strip() and not line.strip().startswith("%%")]
        label = f"Diagram {number}"
        first = lines[0] if lines else ""
        if first.split(" ")[0] not in DIAGRAM_KINDS:
            problems.append(f"{label} should start with one of: {', '.join(DIAGRAM_KINDS)} (it starts with \"{first[:30]}\").")
        if not any(line.startswith("accTitle:") and line[len("accTitle:"):].strip() for line in lines):
            problems.append(f"{label} needs a line starting with accTitle: that gives it a short title.")
        if not any(re.match(r"accDescr(:\s*\S| *\{)", line) for line in lines):
            problems.append(f"{label} needs a line starting with accDescr: that describes it in a sentence.")
    return problems


def text_of(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def guide_problems(guide, platform_names=None):
    """Plain-language problems with one parsed guide; an empty list means it is fine.

    platform_names: the platform names that exist in the site, or None to skip that check.
    """
    problems = []
    text = text_of(guide.body)
    found = text.count(HELP_LINE)
    if found != 1:
        problems.append(f'The help line "{HELP_LINE}" should appear exactly once, at the end (found {found}).')
    for phrase in banned_phrases_in(text):
        if phrase == "standard" and guide.slug in STANDARD_ALLOWED_IN:
            continue
        problems.append(f'The text contains "{phrase}". Reword it.')
    problems.extend(diagram_problems(guide.body))
    if guide.section not in Section.values:
        problems.append(f"Unknown section '{guide.section}'.")
    if platform_names and guide.platform and guide.platform not in platform_names:
        problems.append(f"Platform '{guide.platform}' is not a platform in the site, so the guide would load without a platform.")
    return problems
