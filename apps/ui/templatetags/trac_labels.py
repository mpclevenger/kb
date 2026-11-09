"""Small colored labels: pills, badges and chips.

Pills:   attribute_pill (+ pill_tone filter), type_pill, section_pill, category_pill, count_tile
Badges:  badge (status and coverage)
Chips:   platform_chip, link_chip, control_pill, driver_pill

Colors live in static/css/trac.css (`.tone-*`, `.type-pill-*`, `.category-*`, `.count-tile-*`).
Layout pieces (callouts, cards, headers, lifecycle) are in trac_ui.
"""

from django import template
from django.utils.text import slugify

from apps.platforms.categories import CATEGORY_KEYS, Category
from apps.wiki.models import Section

register = template.Library()

STATUS_LABELS = {
    "draft": "Draft",
    "in_review": "In review",
    "approved": "Approved",
    "published": "Published",
    "retired": "Retired",
}

COVERAGE_LABELS = {"covered": "Covered", "partial": "Partial", "unmapped": "Unmapped"}

# Badge kinds: (value used when the given one is unknown, label for each value).
BADGES = {
    "status": ("draft", STATUS_LABELS),
    "coverage": ("unmapped", COVERAGE_LABELS),
}

PILL_TONES = frozenset(
    {"preventive", "detective", "manual", "automated", "it_dependent", "frequency",
     "key", "sox", "owner", "scope"}
)

LINK_KINDS = {
    "risk": "Risk",
    "control": "Control",
    "driver": "Driver",
}

COUNT_TONES = frozenset({"control", "risk", "alert", "neutral"})


def to_key(value):
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


@register.filter
def pill_tone(value, kind=""):
    key = to_key(value) if value is not None else ""
    if kind == "frequency":
        return "frequency" if key else ""
    if kind in ("nature", "method") and key in PILL_TONES:
        return key
    return ""


@register.inclusion_tag("components/attribute_pill.html")
def attribute_pill(label, value, tone=None):
    key = to_key(tone) if tone else ""
    return {"label": label, "value": value, "tone": key if key in PILL_TONES else ""}


@register.inclusion_tag("components/badge.html")
def badge(kind, value, label=None):
    """A status or coverage badge. Unknown values show as Draft / Unmapped."""
    fallback, labels = BADGES[kind]
    key = to_key(value)
    if key not in labels:
        key = fallback
    return {"kind": kind, "value": key, "label": label or labels[key]}


@register.inclusion_tag("components/platform_chip.html")
def platform_chip(item, category=None):
    """A link chip for a platform (or anything with a name and get_absolute_url, such as a topic).
    Pass a category key to color the chip like that category."""
    return {"name": item.name, "url": item.get_absolute_url(), "category": category}


@register.inclusion_tag("components/link_chip.html")
def link_chip(kind, ident, title, url="#"):
    key = to_key(kind)
    return {
        "kind": key,
        "kind_label": LINK_KINDS.get(key, str(kind).capitalize()),
        "ident": ident,
        "title": title,
        "url": url,
    }


@register.inclusion_tag("components/control_pill.html")
def control_pill(ident, title=None, url=None):
    return {"ident": ident, "title": title, "url": url}


@register.inclusion_tag("components/driver_pill.html")
def driver_pill(ident, url, title=""):
    """A small link showing a risk driver's id (RD01); the title shows when hovering."""
    return {"ident": ident, "url": url, "title": title}


@register.inclusion_tag("components/type_pill.html")
def type_pill(label):
    """A content type label (Control, Risk, Driver) in its color."""
    return {"label": label, "key": slugify(label)}


@register.inclusion_tag("components/type_pill.html")
def section_pill(section):
    """A guide section label (Build your controls, Audit prep, ...) in its color."""
    return {"label": Section(section).label, "key": f"section-{section}"}


@register.inclusion_tag("components/category_pill.html")
def category_pill(category):
    """A category label in its color, linking to the category page."""
    key = str(category)
    return {"key": key, "label": Category(key).label} if key in CATEGORY_KEYS else {}


@register.inclusion_tag("components/count_tile.html")
def count_tile(label, value, tone="neutral"):
    """A count with its label. The alert tone only stands out when there is something to act on."""
    if tone not in COUNT_TONES or (tone == "alert" and not value):
        tone = "neutral"
    return {"label": label, "value": value, "tone": tone}
