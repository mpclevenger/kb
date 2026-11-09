"""Sample data for the component gallery page (ui/gallery.html). Placeholder text only."""

from types import SimpleNamespace

from django.urls import reverse

from apps.platforms.categories import Category
from apps.wiki.models import Section

from .bands import make_band
from .templatetags.trac_ui import TOPIC_ICONS

DEMO_STAGES = [
    {"name": "Roles to permissions", "url": "#"},
    {"name": "Provisioning", "url": "#"},
    {"name": "Periodic review", "url": "#"},
    {"name": "Deprovisioning", "url": "#"},
]

SEVEN_STAGES = [
    {"name": n}
    for n in ("Identify", "Assess", "Design", "Implement", "Operate", "Monitor", "Retire")
]

THREE_STAGES = [
    {"name": "Draft", "url": "#"},
    {"name": "Review", "url": "#"},
    {"name": "Publish", "url": "#"},
]

ARROW_STAGES = [
    {"id": i, "name": name, "url": "#"}
    for i, name in enumerate(("Roles to permissions", "Provisioning", "Periodic review", "Deprovisioning"), start=1)
]

CRITERIA_GROUPS = [
    {"name": "Design", "items": [
        "Example criterion describing a well-designed control.",
        "Example criterion about clear ownership.",
        {"text": "Example criterion that applies only to SOX apps.", "sox_only": True},
    ]},
    {"name": "Evidence", "items": [
        "Example criterion about retained evidence.",
        "Example criterion about review timing.",
    ]},
]


MORE_GROUPS = [
    SimpleNamespace(label="Non-key", items=["CTL-003", "CTL-004"]),
    SimpleNamespace(label="Supporting", items=["CTL-005"]),
]


def sample_context():
    return {
        "band": make_band(
            crumbs=[("Home", "/"), ("Access management", "#"), ("Component gallery", None)],
            icon="key",
            stages=DEMO_STAGES,
            active_stage="Periodic review",
        ),
        "titled_band": make_band(
            crumbs=[("Home", "/"), ("Library", reverse("topics:index")), ("Example page", None)],
            title="Example page title",
            summary="A sentence or two that says what this page is for.",
            icon="key",
            action=("Example action", "#"),
        ),
        "seven_stages": SEVEN_STAGES,
        "three_stages": THREE_STAGES,
        "arrow_stages": ARROW_STAGES,
        "criteria_groups": CRITERIA_GROUPS,
        "more_groups": MORE_GROUPS,
        "icon_names": sorted(TOPIC_ICONS),
        "sample_platform": SimpleNamespace(name="Example platform", get_absolute_url=lambda: "#"),
        "section_keys": Section.values,
        "category_keys": Category.values,
        "sample_bullets": "A sentence before the list.\n- First point\n- Second point",
        "sample_references": [{"label": "Example reference", "url": "#"}],
    }
