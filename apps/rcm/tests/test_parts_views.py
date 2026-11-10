"""Checks how a control page shows level, platforms and the configuration and monitoring parts."""

import html as htmllib
import json
import re

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.platforms.models import Platform
from apps.rcm import services
from apps.rcm.models import Control

from apps.core.tests.support import control_post, publish, published_control

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


@pytest.fixture
def platforms():
    call_command("seed_platforms")
    return Platform.objects


def text_of(response):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", response.content.decode())))


PARTS_CRITERIA = [
    {"name": "Always", "items": ["Owned by a named team."]},
    {"name": "Set up", "part": "configuration", "items": ["Backups are on.", {"text": "Encrypted.", "sox_only": True}]},
    {"name": "Checked", "part": "monitoring", "items": ["Failures raise an alert."]},
]


def published_with_parts(access, owner, reviewer, platform_list=(), **content):
    base = dict(
        frequency="monthly", criteria=PARTS_CRITERIA, level="key", categories=["database", "operating_system"],
        steps=[
            {"role": "Owner", "text": "Check the settings.", "evidence": "Screenshot", "part": "configuration"},
            {"role": "Owner", "text": "Review the alerts.", "evidence": "", "part": "monitoring"},
            {"role": "Owner", "text": "File the evidence.", "evidence": ""},
        ],
    )
    base.update(content)
    entity, version = published_control(access, owner.user, reviewer.user, **base)
    return entity


def tagged_control(access, owner, reviewer, platform_list, **content):
    base = dict(title="Tagged", why="w", owner_role="o", nature="detective", method="manual", frequency="monthly")
    base.update(content)
    entity, version = services.create_control(owner.user, access, **base)
    version.platforms.set(platform_list)
    publish(version, reviewer.user)
    return entity


def test_control_page_shows_level_categories_and_platform_chips(access, owner, reviewer, platforms):
    azure, sql = platforms.get(name="Azure"), platforms.get(name="SQL Server")
    entity = tagged_control(
        access, owner, reviewer, [azure, sql], level="key", categories=["database", "operating_system"]
    )
    html = reviewer.get(entity.get_absolute_url()).content.decode()
    start = html.index('<header class="page-header">')
    header = html[start:html.index("</header>", start)]
    assert "Required for SOX" not in header and "tone-key" in header
    assert "Database" in header and "Operating system" in header
    assert "Applies to:" in header and "Azure" in header and "SQL Server" in header
    assert sql.get_absolute_url().replace("&", "&amp;") in header


def test_no_platform_line_without_platforms(access, owner, reviewer):
    entity = tagged_control(access, owner, reviewer, [], categories=["application"])
    html = reviewer.get(entity.get_absolute_url()).content.decode()
    assert "Applies to:" not in html


def test_control_without_parts_renders_flat(access, owner, reviewer):
    entity, _ = published_control(access, owner.user, reviewer.user)
    html = reviewer.get(entity.get_absolute_url()).content.decode()
    assert "part-heading" not in html
    assert "For SOX apps" not in html


def test_control_with_parts_shows_two_subsections_in_both_cards(access, owner, reviewer):
    entity = published_with_parts(access, owner, reviewer)
    response = reviewer.get(entity.get_absolute_url())
    html = response.content.decode()
    assert html.count('class="part-heading"') == 4
    text = text_of(response)
    assert "Configuration — checked at setup, on any change, and yearly" in text
    assert "Monitoring — checked every month" in text
    good = html[html.index('id="good"'):html.index('id="run"')]
    assert good.index("Owned by a named team.") < good.index("Configuration") < good.index("Backups are on.")
    assert good.index("Backups are on.") < good.index("Monitoring") < good.index("Failures raise an alert.")
    run = html[html.index('id="run"'):]
    assert run.index("File the evidence.") < run.index("Check the settings.") < run.index("Review the alerts.")


def test_sox_only_pill_and_legend(access, owner, reviewer):
    entity = published_with_parts(access, owner, reviewer)
    response = reviewer.get(entity.get_absolute_url())
    html = response.content.decode()
    assert html.count('class="sox-only-pill"') == 1
    assert re.search(r"Encrypted\.\s*<span class=\"sox-only-pill\">For SOX apps</span>", html)
    assert (
        "Lines marked For SOX apps apply when the system is on the firm's SOX in-scope list; otherwise they are recommended."
        in text_of(response)
    )


def test_no_legend_without_sox_only_items(access, owner, reviewer):
    entity, _ = published_control(access, owner.user, reviewer.user, criteria=[{"name": "A", "items": ["one"]}])
    assert "criteria-legend" not in reviewer.get(entity.get_absolute_url()).content.decode()


# Control form

def test_form_renders_new_fields_and_part_controls(owner, access, platforms):
    html = owner.get(reverse("rcm:control_new")).content.decode()
    assert 'name="level"' in html and "Non-key" in html and 'name="scope"' not in html and "Required for SOX" not in html
    assert 'name="categories"' in html and "Logging and monitoring" in html
    assert 'name="platforms"' in html and "<optgroup" in html and 'label="Cloud and containers"' in html
    assert html.count('data-field="part"') == 2 and 'data-field="sox_only"' in html


def test_form_offers_only_active_platforms(owner, access, platforms):
    Platform.objects.filter(name="Splunk").update(is_active=False)
    html = owner.get(reverse("rcm:control_new")).content.decode()
    assert ">Splunk<" not in html and 'label="Logging and monitoring"' not in html and ">AWS<" in html


def test_create_round_trips_parts_sox_only_categories_platforms(owner, access, platforms):
    azure, sql = platforms.get(name="Azure"), platforms.get(name="SQL Server")
    criteria = [
        {"name": "Set up", "part": "configuration", "items": ["Backups are on.", {"text": "Encrypted.", "sox_only": True}]},
        {"name": "Checked", "part": "", "items": [{"text": " Alerts. ", "sox_only": False}]},
    ]
    steps = [{"role": "Owner", "text": "Check.", "evidence": "", "part": "monitoring"},
             {"role": "", "text": "Then file.", "evidence": "", "part": ""}]
    post = control_post(
        access, level="key", categories=["database", "network"], platforms=[azure.pk, sql.pk],
        criteria=json.dumps(criteria), steps=json.dumps(steps),
    )
    response = owner.post(reverse("rcm:control_new"), post)
    assert response.status_code == 302
    version = Control.objects.get().versions.get()
    assert version.level == "key" and version.categories == ["database", "network"]
    assert set(version.platforms.all()) == {azure, sql}
    assert version.criteria == [
        {"name": "Set up", "part": "configuration", "items": ["Backups are on.", {"text": "Encrypted.", "sox_only": True}]},
        {"name": "Checked", "items": ["Alerts."]},
    ]
    assert version.steps == [
        {"role": "Owner", "text": "Check.", "evidence": "", "part": "monitoring"},
        {"role": "", "text": "Then file.", "evidence": ""},
    ]
    form = owner.get(f"{reverse('rcm:control_edit', args=[version.entity.ident])}").context["form"]
    assert set(form.initial["platforms"]) == {azure.pk, sql.pk}
    assert form.initial["categories"] == ["database", "network"]


def test_level_is_saved_from_the_form(owner, access):
    owner.post(reverse("rcm:control_new"), control_post(access, level="supporting"))
    assert Control.objects.get().versions.get().level == "supporting"


def test_unknown_level_is_rejected(owner, access):
    response = owner.post(reverse("rcm:control_new"), control_post(access, level="made-up"))
    assert response.status_code == 200 and not Control.objects.exists()


@pytest.mark.parametrize(
    "field, rows, message",
    [
        ("criteria", [{"name": "G", "part": "weekly", "items": ["x"]}], "Group 1 (G): pick Configuration"),
        ("steps", [{"role": "", "text": "Do it", "evidence": "", "part": "weekly"}], "Step 1: pick Configuration"),
    ],
)
def test_invalid_part_is_rejected_and_rows_kept(owner, access, field, rows, message):
    raw = json.dumps(rows)
    response = owner.post(reverse("rcm:control_new"), control_post(access, **{field: raw}))
    assert response.status_code == 200
    errors = response.context["form"].errors[field]
    assert any(message in e for e in errors)
    assert not Control.objects.exists()
    assert 'name="%s"' % field in response.content.decode()
    assert response.context["form"][field].value() == raw


def test_invalid_sox_only_flag_is_rejected(owner, access):
    bad = json.dumps([{"name": "G", "items": [{"text": "x", "sox_only": "yes"}]}])
    response = owner.post(reverse("rcm:control_new"), control_post(access, criteria=bad))
    assert response.status_code == 200 and "criteria" in response.context["form"].errors


def test_invalid_category_and_platform_are_rejected(owner, access, platforms):
    response = owner.post(reverse("rcm:control_new"), control_post(access, categories=["mainframe"], platforms=[99999]))
    form = response.context["form"]
    assert "categories" in form.errors and "platforms" in form.errors


def test_editing_published_control_copies_platforms_then_updates_draft(owner, reviewer, access, platforms):
    azure, sql = platforms.get(name="Azure"), platforms.get(name="SQL Server")
    entity, v1 = services.create_control(
        owner.user, access, title="T", why="w", owner_role="o", nature="detective", method="manual", frequency="monthly",
    )
    v1.platforms.set([azure])
    publish(v1, reviewer.user)
    response = owner.get(reverse("rcm:control_edit", args=[entity.ident]))
    assert response.context["form"].initial["platforms"] == [azure.pk]
    post = control_post(access, platforms=[sql.pk], change_summary="Retag")
    assert owner.post(reverse("rcm:control_edit", args=[entity.ident]), post).status_code == 302
    draft = entity.versions.get(number=2)
    assert list(draft.platforms.all()) == [sql]
    assert list(entity.versions.get(number=1).platforms.all()) == [azure]
