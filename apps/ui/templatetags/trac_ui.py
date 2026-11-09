"""Page layout and components: callouts, section cards, steps, page header, band, lifecycle, footer, nav.

Callouts and cards:  callout, section_card, section_toolbar, criteria_list, step_list + step, empty_state
Page frame:          page_header, band, primary_nav, governance_footer, topic_icon
Lifecycle:           lifecycle_strip (band), lifecycle_arrows (topic page), stage_step
Text:                bullets (filter: lines starting with "- " become a bullet list)
Colored labels (pills, badges, chips) are in trac_labels.
"""

import datetime
import re

from django import template
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.text import slugify

from apps.core.links import reverse_if_exists

from .trac_labels import STATUS_LABELS, to_key

register = template.Library()

CALLOUT_TYPES = {
    "auditor_tip": "Auditor tip",
    "common_deficiency": "Common deficiency",
    "key_control": "Key control",
    "note": "Note",
    "warning": "Warning",
}

SECTION_TONES = frozenset({"why", "need", "good", "how", "neutral"})

TOPIC_ICONS = frozenset(
    {"key", "git-branch", "file-search", "bug", "cloud", "lifebuoy", "building", "lock", "checklist", "network"}
)

# (key, label, route name or "#"). A route that doesn't exist yet is left out.
PRIMARY_NAV = [
    ("library", "Library", "core:home"),
    ("guides", "Best practices and guides", "wiki:index"),
    ("rcm", "Risks and controls", "rcm:explorer"),
    ("review", "Review queue", "review:queue"),
]
TECH_RISK_ONLY_NAV = frozenset({"rcm", "review"})

# The lifecycle colors are four blues, light to deep (see topics.css).
STAGE_STEPS = 4


# [text](target) in content files becomes a link, but only for TRAC pages ("/..."), places on the
# same page ("#...", including #todo- placeholders for other teams' documents) and https sites.
_LINK = re.compile(r"\[([^\]]+)\]\((#[\w-]+|/[\w/#.-]*|https://[^\s)]+)\)")


@register.filter
def links(text):
    """Text with any [text](target) turned into a link. Everything else is escaped."""
    text, out, last = str(text), [], 0
    for match in _LINK.finditer(text):
        out.append(conditional_escape(text[last:match.start()]))
        out.append(format_html('<a href="{}">{}</a>', match.group(2), match.group(1)))
        last = match.end()
    out.append(conditional_escape(text[last:]))
    return mark_safe("".join(out))


@register.filter
def bullets(text):
    """Guidance text as HTML: lines starting with "- " become a bullet list, other lines stay a paragraph.

    Everything typed is escaped, so content files and the edit form cannot add HTML. A line that starts
    with a space continues the bullet above it.
    """
    blocks = []  # [kind, [lines]] where kind is "ul" or "p"
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            blocks.append(None)
            continue
        if line.startswith("- "):
            kind, line = "ul", line[2:].strip()
        elif raw[0].isspace() and blocks and blocks[-1] and blocks[-1][0] == "ul":
            blocks[-1][1][-1] += " " + line
            continue
        else:
            kind = "p"
        if blocks and blocks[-1] and blocks[-1][0] == kind:
            blocks[-1][1].append(line)
        else:
            blocks.append([kind, [line]])
    html = []
    for block in filter(None, blocks):
        kind, lines = block
        if kind == "ul":
            html.append(format_html("<ul>{}</ul>", format_html_join("", "<li>{}</li>", ((links(line),) for line in lines))))
        else:
            html.append(format_html("<p>{}</p>", mark_safe("<br>".join(links(line) for line in lines))))
    return mark_safe("".join(html))


def _as_date(value):
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return parse_date(value)
    return None


# Callouts and cards

@register.simple_block_tag
def callout(content, type="note", title=None):
    key = to_key(type)
    if key not in CALLOUT_TYPES:
        key = "note"
    return render_to_string(
        "components/callout.html",
        {"type": key, "title": title or CALLOUT_TYPES[key], "content": content},
    )


@register.simple_block_tag
def section_card(content, title, tone="neutral", open=True, id=None):
    key = to_key(tone)
    if key not in SECTION_TONES:
        key = "neutral"
    return render_to_string(
        "components/section_card.html",
        {
            "title": title,
            "tone": key,
            "open": bool(open),
            "heading_id": id or f"section-{slugify(title)}",
            "content": content,
        },
    )


@register.simple_block_tag
def more_controls(content, groups):
    """The folded "More controls (N)" box. `groups` is the LevelGroup list from selectors.fold_by_level.

    The page fills the box with each group's label and items, so each page keeps its own row style.
    """
    count = sum(len(group.items) for group in groups)
    return render_to_string("components/more_controls.html", {"count": count, "content": content})


@register.inclusion_tag("components/section_toolbar.html")
def section_toolbar():
    return {}


def _criterion(item):
    if isinstance(item, dict):
        return {"text": item.get("text", ""), "sox_only": bool(item.get("sox_only"))}
    return {"text": item, "sox_only": False}


@register.inclusion_tag("components/criteria_list.html")
def criteria_list(groups):
    return {
        "groups": [
            {"name": g.get("name"), "items": [_criterion(i) for i in (g.get("items") or [])]}
            for g in (groups or [])
        ]
    }


@register.simple_block_tag
def step(content, role=None):
    return render_to_string("components/step_item.html", {"role": role, "content": content})


@register.simple_block_tag
def step_list(content):
    return render_to_string("components/step_list.html", {"items_html": content})


@register.inclusion_tag("components/empty_state.html")
def empty_state(headline, text=None, action_label=None, action_url="#"):
    return {"headline": headline, "text": text, "action_label": action_label, "action_url": action_url}


# Page frame

def _parse_pills(pills):
    parsed = []
    if not pills:
        return parsed
    items = pills.split(",") if isinstance(pills, str) else pills
    for item in items:
        if isinstance(item, (tuple, list)):
            label, value = item
        else:
            label, sep, value = str(item).partition(":")
            if not sep:
                label, value = "", label
        parsed.append({"label": label.strip(), "value": str(value).strip()})
    return parsed


@register.simple_block_tag
def page_header(content, title, ident=None, status=None, pills=None):
    status_key = to_key(status) if status else None
    return render_to_string(
        "components/page_header.html",
        {
            "title": title,
            "ident": ident,
            "status": status_key if status_key in STATUS_LABELS else None,
            "pills": _parse_pills(pills),
            "actions": content,
        },
    )


@register.simple_block_tag
def band(content):
    """The colored strip under the top bar. Nothing is drawn when the content is blank."""
    if not content.strip():
        return ""
    return render_to_string("components/band.html", {"content": mark_safe(content)})


@register.simple_tag
def topic_icon(name):
    key = str(name).strip().lower()
    if key not in TOPIC_ICONS:
        return ""
    return mark_safe(render_to_string(f"components/icons/{key}.html").strip())


@register.inclusion_tag("components/governance_footer.html")
def governance_footer(version, effective_date, approver, owner, next_review):
    review = _as_date(next_review)
    overdue = bool(review and review < timezone.localdate())
    return {
        "version": version,
        "effective_date": _as_date(effective_date),
        "approver": approver,
        "owner": owner,
        "next_review": review,
        "overdue": overdue,
    }


@register.inclusion_tag("components/primary_nav.html", takes_context=True)
def primary_nav(context):
    active = context.get("nav_active")
    is_tech_risk = bool(context.get("is_tech_risk"))
    links = [(key, label, target if target == "#" else reverse_if_exists(target)) for key, label, target in PRIMARY_NAV]
    return {
        "items": [
            (key, label, href, key == active)
            for key, label, href in links
            if href and (is_tech_risk or key not in TECH_RISK_ONLY_NAV)
        ]
    }


# Lifecycle. The strip and the arrows list the same stages but look too different (flat cells on the
# band versus numbered blue arrows that load a stage in place) to be one component with an option.
# They share how a stage list is read, so the two cannot drift apart.

@register.simple_tag
def stage_step(index, total):
    """Which of the four blue steps (1 lightest, 4 deepest) a lifecycle stage uses; index starts at 0."""
    if total < 2:
        return 1
    return 1 + round(index * (STAGE_STEPS - 1) / (total - 1))


def _stage_field(stage, field):
    if isinstance(stage, dict):
        return stage.get(field)
    return getattr(stage, field, None)


def _lifecycle_items(stages, field, active):
    """Plain dicts for the templates. `active` is compared with each stage's `field` ("name" or "id")."""
    stages = list(stages or [])
    return [
        {
            "id": _stage_field(stage, "id"),
            "name": _stage_field(stage, "name"),
            "url": _stage_field(stage, "url"),
            "number": i + 1,
            "step": stage_step(i, len(stages)),
            "active": active is not None and _stage_field(stage, field) == active,
        }
        for i, stage in enumerate(stages)
    ]


@register.inclusion_tag("components/lifecycle_strip.html")
def lifecycle_strip(stages, active=None):
    """Flat row of stages for a band; `active` is a stage name. Stages without a url are not links."""
    return {"stages": _lifecycle_items(stages, "name", active)}


@register.inclusion_tag("components/lifecycle_arrows.html")
def lifecycle_arrows(stages, active_id, target):
    """Clickable arrows for `stages` (dicts with id, name, url); `target` is the CSS selector HTMX swaps."""
    return {"arrows": _lifecycle_items(stages, "id", active_id), "target": target}
