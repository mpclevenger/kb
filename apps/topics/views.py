"""Library pages: the topic index and one page per topic."""

from collections import Counter

from django.db.models import prefetch_related_objects
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.vary import vary_on_headers

from apps.accounts import permissions
from apps.platforms.models import Platform
from apps.rcm import selectors
from apps.ui.bands import make_band
from apps.wiki.selectors import faq_groups

from .models import Topic

can_view = permissions.permission_required_for(permissions.can_view)

TYPE_FILTERS = [("all", "All"), ("controls", "Controls"), ("risks", "Risks")]
KIND_ORDER = [key for key, _ in TYPE_FILTERS[1:]]


def _topic_faqs(topic):
    """Published FAQ versions for this topic (questions that apply everywhere are not listed here)."""
    for faq_topic, items in faq_groups():
        if faq_topic == topic:
            return [version for _, version, _ in items]
    return []


def _register_rows(kind, type_label, pairs):
    return [
        {
            "kind": kind,
            "type_label": type_label,
            "ident": entity.ident,
            "title": version.title,
            "url": entity.get_absolute_url(),
            "stage_id": version.stage_id,
            "theme_id": version.theme_id,
            "level": getattr(version, "level", ""),
        }
        for entity, version in pairs
    ]


def _unmapped_risk_count(topic):
    """Risks in the topic with no control. Needs the full risk-to-control matrix, so only the whole page asks."""
    return sum(
        row.coverage == "unmapped" for row in selectors.risk_control_matrix() if row.version.topic_id == topic.pk
    )


def _applies_to(topic_controls):
    """Active platforms the topic's controls apply to, as (platform, first category) pairs.

    A control applies to the platforms it is tagged with and to every platform in its categories.
    """
    prefetch_related_objects([version for _, version in topic_controls], "platforms")
    tagged = {p.pk for _, version in topic_controls for p in version.platforms.all()}
    categories = {c for _, version in topic_controls for c in version.categories}
    return [
        (platform, platform.primary_category)
        for platform in Platform.objects.filter(is_active=True)
        if platform.pk in tagged or categories.intersection(platform.categories)
    ]


def _group(controls, risks, match):
    """The risks that match, and the matching controls: open levels shown, the other levels folded."""
    shown, more = selectors.fold_by_level([c for c in controls if match(c)], lambda c: c["level"])
    return {"controls": shown, "more": more, "risks": [r for r in risks if match(r)]}


def _stage_panel(stage, controls, risks):
    return {"stage": stage, **_group(controls, risks, lambda i: i["stage_id"] == stage.pk)}


def _throughout(themes, controls, risks):
    """One group per theme, plus the items with neither a stage nor a theme."""
    boxes = [
        {"theme": theme, **_group(controls, risks, lambda i, t=theme: i["theme_id"] == t.pk)}
        for theme in themes
    ]
    whole = _group(controls, risks, lambda i: not i["stage_id"] and not i["theme_id"])
    return boxes, whole if any(whole.values()) else None


@can_view
def index(request):
    topics = list(Topic.objects.filter(is_active=True).prefetch_related("stages"))
    control_counts = Counter(v.topic_id for _, v in selectors.current_controls())
    risk_counts = Counter(v.topic_id for _, v in selectors.current_risks())
    tiles = [
        {
            "topic": t,
            "controls": control_counts[t.pk],
            "risks": risk_counts[t.pk],
            "stages": len(t.stages.all()),
        }
        for t in topics
    ]
    return render(
        request,
        "topics/index.html",
        {
            "nav_active": "library",
            "tiles": tiles,
            "band": make_band(
                [("Home", "/"), ("Library", None)],
                title="Library",
                summary="Start with a topic. Each one shows what can go wrong and the controls that address it.",
            ),
        },
    )


@can_view
@vary_on_headers("HX-Request", "HX-Target")
def detail(request, slug):
    topic = get_object_or_404(Topic, slug=slug, is_active=True)
    stages = list(topic.stages.all())
    topic_controls = [(c, v) for c, v in selectors.current_controls() if v.topic_id == topic.pk]
    topic_risks = [(r, v) for r, v in selectors.current_risks() if v.topic_id == topic.pk]
    controls = _register_rows("controls", "Control", topic_controls)
    risks = _register_rows("risks", "Risk", topic_risks)

    selected = next((s for s in stages if str(s.pk) == request.GET.get("stage")), stages[0] if stages else None)
    type_key = request.GET.get("type")
    if type_key not in dict(TYPE_FILTERS):
        type_key = "all"

    stage_names = {s.pk: s.name for s in stages}
    items = sorted(controls + risks, key=lambda i: (KIND_ORDER.index(i["kind"]), i["ident"], i["title"].lower()))
    for item in items:
        item["stage_name"] = stage_names.get(item["stage_id"])
    type_counts = Counter(i["kind"] for i in items)
    # Controls at open levels and risks are listed; the other controls are folded under "More controls".
    shown_controls, more_controls = selectors.fold_by_level(
        [i for i in controls if type_key in ("all", "controls")], lambda i: i["level"]
    )
    shown_risks = [i for i in risks if type_key in ("all", "risks")]
    base_url = reverse("topics:detail", args=[topic.slug])
    query = f"stage={selected.pk}&" if selected else ""
    context = {
        "nav_active": "library",
        "topic": topic,
        "stage": selected,
        "stages": [{"id": s.pk, "name": s.name, "url": f"{base_url}?stage={s.pk}"} for s in stages],
        "type_key": type_key,
        "filters": [
            {
                "key": key,
                "label": label,
                "count": len(items) if key == "all" else type_counts[key],
                "active": key == type_key,
            }
            for key, label in TYPE_FILTERS
        ],
        "items": shown_controls + shown_risks,
        "more": more_controls,
        "base_url": base_url,
        "query": query,
    }
    if selected:
        context["selected_index"] = stages.index(selected)
        context["panel"] = _stage_panel(selected, controls, risks)
    if request.headers.get("HX-Request"):
        template = "topics/_everything.html" if request.headers.get("HX-Target") == "everything" else "topics/_lifecycle.html"
        return render(request, template, context)

    theme_boxes, whole_topic = _throughout(list(topic.themes.all()), controls, risks)
    context.update(
        {
            "band": make_band(
                [("Home", "/"), ("Library", reverse("topics:index")), (topic.name, None)],
                title=topic.name,
                summary=topic.summary,
                icon=topic.icon,
            ),
            "applies_to": _applies_to(topic_controls),
            "theme_boxes": theme_boxes,
            "whole_topic": whole_topic,
            "faqs": _topic_faqs(topic),
            "counts": {"controls": len(controls), "risks": len(risks), "unmapped": _unmapped_risk_count(topic)},
        }
    )
    return render(request, "topics/detail.html", context)
