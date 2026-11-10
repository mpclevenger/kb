"""Site-wide search: the matching, ranking and snippet rules, with no database access.

`selectors.search_items()` builds the list of SearchItem (published content only);
this module decides which items match a query and in what order.

The rules, in plain words:
- The query is split into words. Case is ignored and words of 1-2 letters are skipped.
- A word is "known" if it appears anywhere in the site's published content.
  Unknown words (for example an internal app name) are left out, and the page says so.
- An item matches when any remaining word appears in its title or text, so related pages still show
  (for "dashboard Databricks", the report guide shows even though it doesn't mention Databricks).
- Order: items with more of the words first, then more of them in the title, then shorter titles.
- Each group shows its best MAX_PER_GROUP results.
- The snippet is taken around the least common matched word, which is usually the most telling one.
"""

import re
from dataclasses import dataclass, field

from django.utils.html import escape, format_html, strip_tags
from django.utils.safestring import mark_safe

MIN_WORD_LENGTH = 3
SNIPPET_LENGTH = 160
MAX_PER_GROUP = 8
GROUPS = ("guide", "control", "risk", "library", "topic")
GROUP_LABELS = {"guide": "Guides", "control": "Controls", "risk": "Risks", "library": "Library", "topic": "Topics"}


@dataclass
class SearchItem:
    """One thing that can be found: where it goes, what it is called and the text to search."""

    group: str  # one of GROUPS
    title: str
    url: str
    text: str = ""  # everything else worth searching, as plain text
    pill: str = ""  # the label for the type pill (a guide's section key, a control's ID, ...)
    lowered: str = field(init=False, repr=False)
    lowered_title: str = field(init=False, repr=False)

    def __post_init__(self):
        self.lowered_title = self.title.lower()
        self.lowered = f"{self.lowered_title}\n{self.text.lower()}"


@dataclass
class Result:
    item: SearchItem
    snippet: str  # safe HTML: escaped text with <mark> around matched words


_DIAGRAM = re.compile(r'<(pre|div)[^>]*class="[^"]*mermaid[^"]*"[^>]*>.*?</\1>', re.S | re.I)


def plain_text(value):
    """HTML (or plain text) as one line of plain text: diagram source is left out, and block ends become spaces."""
    html = _DIAGRAM.sub(" ", str(value or ""))
    html = re.sub(r"</(p|li|h[1-6]|div|td|th|tr|pre|blockquote)>|<br\s*/?>", " ", html, flags=re.I)
    return re.sub(r"\s+", " ", strip_tags(html)).strip()


def query_words(query):
    """The distinct words of a query, lower case, without 1-2 letter words, in the order typed."""
    words = []
    for word in re.findall(r"\w+", (query or "").lower()):
        if len(word) >= MIN_WORD_LENGTH and word not in words:
            words.append(word)
    return words


def snippet_for(item, words, rarest_first=None):
    """A short piece of the item's text around a matched word, safe to show as HTML.

    `rarest_first` is the query words, least common first; the snippet centers on the first of
    them found in the text. Without it, the first matched word is used.
    """
    text = item.text
    pattern = re.compile("|".join(re.escape(word) for word in words), re.IGNORECASE)
    lowered = text.lower()
    present = [word for word in (rarest_first or []) if word in lowered]
    if present:  # the word used least in this item's own text, ties going to the one less common site-wide
        word = min(present, key=lambda w: (lowered.count(w), present.index(w)))
        found = re.search(re.escape(word), text, re.IGNORECASE)
    else:
        found = pattern.search(text)
    start = 0
    if found and found.start() > SNIPPET_LENGTH // 3:
        start = max(text.rfind(" ", 0, found.start() - SNIPPET_LENGTH // 3) + 1, 0)  # begin on a whole word
    piece = text[start:start + SNIPPET_LENGTH]
    if start + SNIPPET_LENGTH < len(text):
        piece = piece.rsplit(" ", 1)[0] + "..." if " " in piece else piece + "..."
    if start:
        piece = "..." + piece
    parts, last = [], 0
    for match in pattern.finditer(piece):
        parts.append(escape(piece[last:match.start()]))
        parts.append(format_html("<mark>{}</mark>", match.group()))
        last = match.end()
    parts.append(escape(piece[last:]))
    return mark_safe("".join(parts))  # every part above is already escaped


def run_search(query, items):
    """Search `items` (a list of SearchItem).

    Returns (results, left_out): results is {group: [Result]} for the groups that have any,
    in display order; left_out is the query words that appear nowhere on the site.
    """
    words = query_words(query)
    if not words:
        return {}, []
    known = [word for word in words if any(word in item.lowered for item in items)]
    left_out = [word for word in words if word not in known]
    if not known:
        return {}, left_out
    matches = [item for item in items if any(word in item.lowered for word in known)]
    how_common = {word: sum(word in item.lowered for item in items) for word in known}
    rarest_first = sorted(known, key=lambda word: how_common[word])

    def order(item):
        words_found = sum(word in item.lowered for word in known)
        title_words = sum(word in item.lowered_title for word in known)
        return (-words_found, -title_words, len(item.title), item.lowered_title)

    results = {group: [] for group in GROUPS}
    for item in sorted(matches, key=order):
        if len(results[item.group]) < MAX_PER_GROUP:
            results[item.group].append(Result(item, snippet_for(item, known, rarest_first)))
    return {group: found for group, found in results.items() if found}, left_out
