"""Checks the shared page pieces (callouts, cards, pills) and that the gallery shows every one."""

import re
import datetime

import pytest
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from apps.core.links import reverse_if_exists


def render(source, **context):
    return Template("{% load trac_ui trac_labels %}" + source).render(Context(context))


@pytest.mark.django_db
def test_gallery_renders_every_component(client):
    response = client.get(reverse("ui:gallery"))
    assert response.status_code == 200
    html = response.content.decode()
    for marker in (
        "page-header", "callout", "attr-pill", "trac-badge-status", "trac-badge-coverage", "link-chip",
        "step-list", "governance-footer", "empty-state", "trac-table", "page-rail",
        "control-pill", "lifecycle-strip", "lifecycle-arrows", "criteria", "topic-icon", "trac-band", "trac-paper",
        "section-card", "section-toolbar", "platform-chip", "type-pill", "category-pill", "count-tile",
        "library-tabs", "category-cards", "references", "band-title", "band-crumbs",
    ):
        assert f'class="{marker}' in html or f" {marker}" in html, marker


def test_gallery_shows_every_tag():
    """A new template tag must get a sample in the gallery. primary_nav and band are drawn by base.html on
    every page; stage_step is a helper for the topic stage panel."""
    from pathlib import Path

    from apps.platforms.templatetags import platform_cards
    from apps.ui.templatetags import trac_labels, trac_ui

    gallery = (Path(__file__).resolve().parents[1] / "templates" / "ui" / "gallery.html").read_text()
    skipped = {"primary_nav", "band", "stage_step"}
    for library in (trac_ui, trac_labels, platform_cards):
        for name in library.register.tags:
            if name not in skipped:
                assert f"{{% {name} " in gallery or f"{{% {name} %}}" in gallery, name


@pytest.mark.parametrize(
    "kind,title",
    [
        ("auditor_tip", "Auditor tip"),
        ("common_deficiency", "Common deficiency"),
        ("key_control", "Key control"),
        ("note", "Note"),
        ("warning", "Warning"),
    ],
)
def test_callout_variants(kind, title):
    html = render(f'{{% callout "{kind}" %}}<p>Body</p>{{% endcallout %}}')
    assert f"callout-{kind}" in html
    assert f'callout-title">{title}<' in html
    assert "<p>Body</p>" in html


def test_callout_unknown_type_falls_back_to_note():
    assert "callout-note" in render('{% callout "bogus" %}x{% endcallout %}')


def test_callout_custom_title():
    assert "Custom" in render('{% callout "note" title="Custom" %}x{% endcallout %}')


@pytest.mark.parametrize("tone", ["why", "need", "good", "how", "neutral"])
def test_section_card_tones(tone):
    html = render(f'{{% section_card "Title here" tone="{tone}" %}}<p>Body</p>{{% endsection_card %}}')
    assert "<details" in html and "<summary" in html and "<h2" in html
    assert f"section-card-{tone}" in html and "<p>Body</p>" in html
    assert 'id="section-title-here"' in html


def test_section_card_open_by_default_and_collapsible():
    assert "<details class=\"section-card section-card-why\" open>" in render('{% section_card "T" tone="why" %}x{% endsection_card %}')
    closed = render('{% section_card "T" tone="why" open=False id="t1" %}x{% endsection_card %}')
    assert " open>" not in closed and 'id="t1"' in closed


def test_section_card_unknown_tone_is_neutral():
    assert "section-card-neutral" in render('{% section_card "T" tone="bogus" %}x{% endsection_card %}')


def test_section_toolbar_has_both_buttons():
    html = render("{% section_toolbar %}")
    assert 'data-sections="expand"' in html and 'data-sections="collapse"' in html and "hidden" in html


@pytest.mark.parametrize(
    "value,kind,tone",
    [
        ("preventive", "nature", "preventive"),
        ("detective", "nature", "detective"),
        ("manual", "method", "manual"),
        ("automated", "method", "automated"),
        ("it_dependent", "method", "it_dependent"),
        ("quarterly", "frequency", "frequency"),
        ("event", "frequency", "frequency"),
        ("other", "nature", ""),
        ("", "frequency", ""),
    ],
)
def test_pill_tone_mapping(value, kind, tone):
    assert render('{{ v|pill_tone:k }}', v=value, k=kind) == tone


def test_attribute_pill_tone_class():
    assert "attr-pill tone-sox" in render('{% attribute_pill "" "SOX scope" tone="sox" %}')
    assert "tone-" not in render('{% attribute_pill "" "X" tone="bogus" %}')
    assert 'class="attr-pill"' in render('{% attribute_pill "A" "B" %}')
    html = render('{% attribute_pill "Method" "Manual" tone=v|pill_tone:"method" %}', v="manual")
    assert "attr-pill tone-manual" in html


@pytest.mark.parametrize("coverage,label", [("covered", "Covered"), ("partial", "Partial"), ("unmapped", "Unmapped")])
def test_coverage_badge(coverage, label):
    html = render(f'{{% badge "coverage" "{coverage}" %}}')
    assert f"trac-badge-coverage tone-{coverage}" in html and label in html


def test_coverage_badge_custom_label_and_fallback():
    assert "Custom" in render('{% badge "coverage" "covered" "Custom" %}')
    html = render('{% badge "coverage" "weird" %}')
    assert "tone-unmapped" in html and "Unmapped" in html


def test_base_loads_ui_script():
    assert "js/trac-ui.js" in render_to_string("base.html", {})


def test_attribute_pill():
    html = render('{% attribute_pill "Frequency" "Monthly" %}')
    assert "attr-pill" in html and "Frequency" in html and "Monthly" in html
    assert "attr-pill-label" not in render('{% attribute_pill "" "Key" %}')


@pytest.mark.parametrize(
    "status,label",
    [("draft", "Draft"), ("in_review", "In review"), ("In review", "In review"),
     ("approved", "Approved"), ("published", "Published"), ("retired", "Retired")],
)
def test_status_badge(status, label):
    html = render('{% badge "status" s %}', s=status)
    assert f">{label}<" in html
    assert "trac-badge-status tone-" + status.lower().replace(" ", "_") in html


def test_status_badge_unknown_status_shows_as_draft():
    assert "tone-draft" in render('{% badge "status" "weird" %}')


@pytest.mark.parametrize("kind,label", [("risk", "Risk"), ("control", "Control"), ("driver", "Driver")])
def test_link_chip(kind, label):
    html = render('{% link_chip kind "ID-1" "Short title" "/x/" %}', kind=kind)
    assert 'class="link-chip"' in html and f'data-kind="{kind}"' in html
    assert f"link-chip-{kind}" not in html
    assert "ID-1" in html and "Short title" in html and label in html
    assert 'href="/x/"' in html


def test_step_list_block_with_and_without_role():
    html = render('{% step_list %}{% step role="Owner" %}One{% endstep %}{% step %}Two{% endstep %}{% endstep_list %}')
    assert html.count("step-list-item") == 2
    assert html.count("step-list-role") == 1
    assert "<ol" in html


def test_step_list_include_with_data():
    html = render_to_string("components/step_list.html", {"steps": [{"text": "A", "role": "R"}, {"text": "B"}]})
    assert html.count("step-list-item") == 2 and ">R<" in html


def test_governance_footer_overdue_for_past_date():
    html = render('{% governance_footer "1.0" "2020-01-01" "Appr" "Own" "2020-06-01" %}')
    assert "governance-footer-overdue" in html
    assert "Overdue" in html
    assert "Jun 1, 2020" in html


def test_governance_footer_not_overdue_for_future_date():
    future = datetime.date.today() + datetime.timedelta(days=60)
    html = render('{% governance_footer "1.0" "2020-01-01" "Appr" "Own" d %}', d=future)
    assert "governance-footer-overdue" not in html
    assert "Overdue" not in html
    for label in ("Version", "Effective date", "Approver", "Owner", "Review by"):
        assert label in html


def test_page_header_variants():
    html = render('{% page_header title="T" ident="X-1" status="published" pills="Key,Frequency:Monthly" %}<a>Go</a>{% endpage_header %}')
    assert "X-1" in html and "<h1" in html and "tone-published" in html
    assert html.count('class="attr-pill"') == 2 and "<a>Go</a>" in html
    bare = render('{% page_header title="T" %}{% endpage_header %}')
    assert "page-header-actions" not in bare and "trac-badge" not in bare


def test_empty_state_with_and_without_action():
    with_action = render('{% empty_state "Head" "Line" action_label="Add" action_url="/a/" %}')
    assert "empty-state" in with_action and "Head" in with_action and 'href="/a/"' in with_action
    assert "btn" not in render('{% empty_state "Head" "Line" %}')


def test_base_renders_without_user_context():
    request = RequestFactory().get("/")
    html = render_to_string("base.html", {}, request=request)
    assert "<main" in html and "<nav" in html and 'role="banner"' not in html
    assert "vendor/htmx.min.js" in html and "hx-headers" in html
    assert "trac-user" not in html
    assert "cdn" not in html.lower()


def test_base_nav_marks_active_item():
    html = render_to_string("base.html", {"nav_active": "library", "is_tech_risk": True})
    assert html.count('aria-current="page"') == 1
    labels = re.findall(r'<li><a href="[^"]*"[^>]*>([^<]+)</a>', html.split('aria-label="Primary"')[1].split("</nav>")[0])
    assert labels[:2] == ["Home", "Library"] and labels[-2:] == ["Risks and controls", "Review queue"]
    assert set(labels) <= {"Home", "Library", "Best practices and guides", "Risks and controls", "Review queue"}
    assert ("Best practices and guides" in labels) == bool(reverse_if_exists("wiki:index"))


def test_nav_has_home_then_library_and_no_dictionary_or_platforms_item():
    html = render_to_string("base.html", {"nav_active": "library"})
    assert 'href="/library/" aria-current="page">Library<' in html
    assert ">Dictionary<" not in html and ">Platforms<" not in html


def test_base_app_switcher_uses_suite_links():
    html = render_to_string("base.html", {"suite_links": {"trust": "https://trust.example/"}})
    assert "https://trust.example/" in html
    assert "trac-switcher" not in render_to_string("base.html", {})


STAGES = [{"name": "One", "url": "/1/"}, {"name": "Two", "url": "/2/"}, {"name": "Three", "url": "/3/"}]


class Stage:
    def __init__(self, name, url=None):
        self.name, self.url = name, url


def test_lifecycle_strip_marks_active_stage_and_links():
    html = render("{% lifecycle_strip stages active %}", stages=STAGES, active="Two")
    assert html.count("lifecycle-stage-label") >= 3
    assert html.count('aria-current="step"') == 1
    assert 'href="/2/" aria-current="step">Two<' in html
    assert 'href="/1/">One<' in html


def test_lifecycle_strip_without_active_or_urls():
    html = render("{% lifecycle_strip stages None %}", stages=[Stage("A"), Stage("B")])
    assert "aria-current" not in html and "<a " not in html
    assert "<span" in html and ">A<" in html


@pytest.mark.parametrize("count", [3, 4, 5, 6, 7])
def test_lifecycle_strip_handles_three_to_seven_stages(count):
    stages = [Stage(f"S{i}", f"/{i}/") for i in range(count)]
    html = render("{% lifecycle_strip stages 'S1' %}", stages=stages)
    assert html.count('class="lifecycle-stage"') == count
    assert html.count('aria-current="step"') == 1


def test_lifecycle_strip_unknown_active_marks_nothing():
    assert "aria-current" not in render("{% lifecycle_strip stages 'Nope' %}", stages=STAGES)


def test_control_pill_with_and_without_title_and_url():
    full = render('{% control_pill "CTL-1" "Title" "/c/" %}')
    assert 'class="control-pill"' in full and 'href="/c/"' in full
    assert "control-pill-id" in full and "Title" in full
    bare = render('{% control_pill "CTL-1" %}')
    assert "<a " not in bare and "control-pill-title" not in bare and "CTL-1" in bare


def test_criteria_list_groups_and_items():
    groups = [{"name": "Design", "items": ["A", "B"]}, {"name": "Evidence", "items": ["C"]}]
    html = render("{% criteria_list groups %}", groups=groups)
    assert html.count("criteria-group-name") == 2
    assert html.count('class="criteria-item"') == 3
    assert "Design" in html and ">C<" in html


def test_criteria_list_escapes_and_handles_empty():
    html = render("{% criteria_list groups %}", groups=[{"name": "G", "items": ["<b>x</b>"]}])
    assert "&lt;b&gt;" in html
    assert "criteria-item" not in render("{% criteria_list groups %}", groups=[])


@pytest.mark.parametrize(
    "name", ["key", "git-branch", "file-search", "bug", "cloud", "lifebuoy", "building", "lock", "checklist"]
)
def test_topic_icon_renders_svg(name):
    html = render("{% topic_icon name %}", name=name)
    assert html.startswith("<svg") and 'viewBox="0 0 24 24"' in html
    assert 'stroke-width="2"' in html and 'stroke="currentColor"' in html
    assert 'width="16"' in html and 'aria-hidden="true"' in html


@pytest.mark.parametrize("name", ["nope", "", "../base"])
def test_topic_icon_unknown_renders_nothing(name):
    assert render("{% topic_icon name %}", name=name).strip() == ""


def test_base_band_renders_only_when_filled():
    request = RequestFactory().get("/")
    assert "trac-band" not in render_to_string("base.html", {}, request=request)
    child = Template(
        '{% extends "base.html" %}{% block band %}<p>Band content</p>{% endblock %}'
    ).render(Context({}))
    assert 'class="trac-band"' in child and "Band content" in child
    whitespace = Template('{% extends "base.html" %}{% block band %}  {% endblock %}').render(Context({}))
    assert "trac-band" not in whitespace


@pytest.mark.django_db
def test_gallery_demo_band_and_new_components(client):
    html = client.get(reverse("ui:gallery")).content.decode()
    assert html.index("trac-band") < html.index("trac-shell")
    assert "Periodic review" in html and 'aria-current="step"' in html
    assert html.count("<svg") >= 10
    assert "What good looks like" in html and "control-pill" in html
    assert "cdn" not in html.lower()


def test_font_files_are_vendored_and_referenced():
    from pathlib import Path
    from django.conf import settings
    css = (Path(settings.BASE_DIR) / "static/css/trac.css").read_text()
    for weight in (400, 500, 600):
        name = f"public-sans-latin-{weight}-normal.woff2"
        assert name in css
        assert (Path(settings.BASE_DIR) / "static/vendor/fonts/public-sans" / name).exists()
    assert "http" not in css


def test_bullets_filter_makes_lists_and_escapes_everything():
    from apps.ui.templatetags.trac_ui import bullets

    assert str(bullets("- One\n- Two")) == "<ul><li>One</li><li>Two</li></ul>"
    assert str(bullets("Plain\ntext")) == "<p>Plain<br>text</p>"
    assert str(bullets("Intro line\n- One\n- Two\n\nAfter")) == "<p>Intro line</p><ul><li>One</li><li>Two</li></ul><p>After</p>"
    assert str(bullets("- A long point\n  that carries on")) == "<ul><li>A long point that carries on</li></ul>"
    assert str(bullets("-not a bullet")) == "<p>-not a bullet</p>"
    assert str(bullets("")) == ""
    html = str(bullets("- <script>alert(1)</script> & more\n<b>bold</b>"))
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp; more" in html and "&lt;b&gt;" in html



def test_links_filter_makes_safe_links_only():
    from apps.ui.templatetags.trac_ui import links

    html = str(links('See [the team page](#todo-security-incident-reporting), [a guide](/guides/x/), '
                     '[docs](https://example.com/a) and [bad](javascript:alert(1)) <b>bold</b>'))
    assert '<a href="#todo-security-incident-reporting">the team page</a>' in html
    assert '<a href="/guides/x/">a guide</a>' in html and '<a href="https://example.com/a">docs</a>' in html
    assert "javascript" not in html.split("[bad]")[0] and "[bad](javascript:alert(1))" in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
