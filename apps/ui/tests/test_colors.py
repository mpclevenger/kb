"""Checks that the pill and category colors are the approved ones and readable."""

import re
from pathlib import Path

import pytest
from django.template import Context, Template, TemplateDoesNotExist
from django.template.loader import get_template

from apps.platforms.categories import Category
from apps.ui.templatetags.trac_ui import stage_step

CSS = (Path(__file__).resolve().parents[3] / "static" / "css" / "trac.css").read_text()
LIFECYCLE_CSS = (Path(__file__).resolve().parents[3] / "static" / "css" / "topics.css").read_text()
PAPER, WHITE, NAVY = "#f3f6f9", "#ffffff", "#1b2a3a"
AA = 4.5


def render(source, **context):
    return Template("{% load trac_labels %}" + source).render(Context(context))


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def css_vars(selector, css=CSS):
    block = re.search(re.escape(selector) + r" \{([^}]*)\}", css).group(1)
    return dict(re.findall(r"(--[\w-]+): (#\w+)", block))


# Type pills

def test_type_pill_names_the_type():
    assert render('{% type_pill "Control" %}') == '<span class="type-pill type-pill-control">Control</span>\n'
    assert 'type-pill-control">Control' in render('{% type_pill "Control" %}')


@pytest.mark.parametrize("key,bg,ink", [
    ("control", "#dce7f3", "#1f4e7a"), ("risk", "#f6dcdc", "#8a2b2b"),
])
def test_type_pill_colors_are_the_approved_pairs_and_readable(key, bg, ink):
    colors = css_vars(f".type-pill-{key}")
    assert (colors["--pill-bg"], colors["--pill-ink"]) == (bg, ink)
    assert contrast(ink, bg) >= AA


# Category pills

def test_category_pill_links_to_the_category_page():
    html = render("{% category_pill key %}", key="jobs")
    assert 'class="category-pill category-jobs"' in html and 'href="/platforms/category/jobs/"' in html
    assert ">Jobs and interfaces</a>" in html


def test_category_pill_ignores_unknown_keys():
    assert render("{% category_pill key %}", key="mainframe").strip() == ""


APPROVED_EDGE_COLORS = {
    "application": "#5b3f8c", "database": "#2f5d8a", "operating_system": "#556677", "jobs": "#9a6b1f",
    "network": "#2e7d5b", "identity": "#8c3f5b", "cloud": "#1f6e7e", "engineering_tools": "#a04a2f",
    "logging": "#5e6b1f",
}


@pytest.mark.parametrize("category", Category.values)
def test_category_colors_are_approved_and_readable(category):
    colors = css_vars(f".category-{category}")
    assert colors["--category"] == APPROVED_EDGE_COLORS[category]
    ink, tint = colors["--category-ink"], colors["--category-tint"]
    assert contrast(ink, tint) >= AA
    assert contrast(ink, PAPER) >= AA and contrast(ink, WHITE) >= AA


def test_every_category_has_colors():
    assert set(APPROVED_EDGE_COLORS) == set(Category.values)


# Stage steps

def test_stage_step_spreads_stages_across_the_four_steps():
    assert [stage_step(i, 1) for i in range(1)] == [1]
    assert [stage_step(i, 2) for i in range(2)] == [1, 4]
    assert [stage_step(i, 4) for i in range(4)] == [1, 2, 3, 4]
    for total in range(2, 9):
        steps = [stage_step(i, total) for i in range(total)]
        assert steps == sorted(steps) and steps[0] == 1 and steps[-1] == 4


@pytest.mark.parametrize("step", [1, 2, 3, 4])
def test_stage_step_colors_are_readable(step):
    colors = css_vars(f".lifecycle-step-{step}", LIFECYCLE_CSS)
    assert contrast(colors["--stage-ink"], colors["--stage-bg"]) >= AA


def test_stage_steps_run_from_light_to_deep_blue():
    backgrounds = [css_vars(f".lifecycle-step-{n}", LIFECYCLE_CSS)["--stage-bg"] for n in (1, 2, 3, 4)]
    assert backgrounds[0] == "#dce7f3" and backgrounds[-1] == "#2f5d8a"
    assert [luminance(c) for c in backgrounds] == sorted((luminance(c) for c in backgrounds), reverse=True)


# Count tiles

def test_count_tile_tones():
    assert "count-tile-control" in render('{% count_tile "Controls" 3 "control" %}')
    assert "count-tile-risk" in render('{% count_tile "Risks" 3 "risk" %}')
    assert "count-tile-alert" in render('{% count_tile "Unmapped risks" 2 "alert" %}')


def test_alert_tile_is_neutral_at_zero_and_unknown_tones_fall_back():
    assert "count-tile-neutral" in render('{% count_tile "Unmapped risks" 0 "alert" %}')
    assert "count-tile-neutral" in render('{% count_tile "Odd" 5 "purple" %}')


@pytest.mark.parametrize("tone,expected_bg", [("alert", "#8a2b2b"), ("control", "#dce7f3"), ("risk", "#f6dcdc")])
def test_count_tile_colors_are_readable(tone, expected_bg):
    colors = css_vars(f".count-tile-{tone}")
    assert colors["--tile-bg"] == expected_bg
    assert contrast(colors["--tile-ink"], colors["--tile-bg"]) >= AA


# Shared form field

def test_field_form_is_a_shared_component():
    assert get_template("components/field_form.html")
    with pytest.raises(TemplateDoesNotExist):
        get_template("rcm/field_form.html")
