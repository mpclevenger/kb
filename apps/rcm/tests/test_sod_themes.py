"""Segregation of duties, themes, evidence rule filtering, the seed command and nav highlighting."""

import json
import re

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import (
    Control,
    ControlVersion,
    EvidenceRule,
    EvidenceRuleVersion,
    Risk,
    RuleAppliesTo,
    rule_applies,
)
from apps.core.tests.support import As, control_post, publish, published_control, risk_post

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

# Scope merge migration

# Roles and the independence guidance

GUIDANCE = "The reviewer must be independent of what they review."


def control_page(viewer, approver, topic, **content):
    control, _ = published_control(topic, viewer.user, approver.user, **content)
    return viewer.get(control.get_absolute_url()).content.decode()


def test_role_fields_round_trip_through_the_form(owner, access):
    data = control_post(access, performer_role="Database administrator", reviewer_role="Application owner")
    assert owner.post(reverse("rcm:control_new"), data).status_code == 302
    version = ControlVersion.objects.get()
    assert (version.owner_role, version.performer_role, version.reviewer_role) == (
        "Identity and Access", "Database administrator", "Application owner"
    )
    html = owner.get(reverse("rcm:control_edit", args=[version.entity.ident])).content.decode()
    assert 'value="Database administrator"' in html and 'value="Application owner"' in html
    for label in ("Owner role", "Performed by (role)", "Reviewed by (role)"):
        assert label in html


def test_independence_fields_are_gone_from_form_and_model(owner):
    html = owner.get(reverse("rcm:control_new")).content.decode()
    for name in ("reviewer_independent", "compensating_check", "trac-sod"):
        assert name not in html
    names = {f.name for f in ControlVersion._meta.get_fields()}
    assert not names & {"reviewer_independent", "compensating_check", "owner", "performer", "reviewer"}


def test_roles_line_and_guidance_when_reviewer_role_is_set(owner, reviewer, access):
    html = control_page(owner, reviewer, access, performer_role="Operations", reviewer_role="Application owner")
    assert "Performed by: <strong>Operations</strong>" in html
    assert "Reviewed by: <strong>Application owner</strong>" in html
    run = html.split('id="run"')[1]
    assert GUIDANCE in run and "write it into your procedure." in run


def test_guidance_shows_even_without_steps(owner, reviewer, access):
    html = control_page(owner, reviewer, access, steps=[], reviewer_role="Application owner")
    assert GUIDANCE in html


def test_no_roles_line_or_guidance_without_roles(owner, reviewer, access):
    html = control_page(owner, reviewer, access)
    assert "Performed by" not in html and "Reviewed by" not in html and GUIDANCE not in html


def test_performer_alone_has_no_guidance(owner, reviewer, access):
    html = control_page(owner, reviewer, access, performer_role="Operations")
    assert "Performed by: <strong>Operations</strong>" in html and GUIDANCE not in html


# One SOX flag per kind

def test_control_shows_level_pill_and_no_sox_scope_pill(owner, reviewer, access):
    html = control_page(owner, reviewer, access, level="key")
    assert "tone-key" in html and ">Key<" in html and "SOX scope" not in html
    plain = control_page(owner, reviewer, access, title="Plain", level="supporting")
    assert ">Supporting<" in plain and "SOX scope" not in plain
    assert "Required for SOX" not in html + plain


def test_control_form_has_no_sox_checkbox_but_risk_form_does(owner):
    assert "In SOX scope" not in owner.get(reverse("rcm:control_new")).content.decode()
    assert "In SOX scope" in owner.get(reverse("rcm:risk_new")).content.decode()


def test_explorer_shows_level_column_not_scope(owner, reviewer, access):
    published_control(access, owner.user, reviewer.user, level="key", title="Top one")
    published_control(access, owner.user, reviewer.user, level="supporting", title="Helper one")
    html = owner.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
    assert '<th scope="col">Level</th>' in html
    assert "Required for SOX" not in html and "Recommended for all" not in html


def test_risk_page_and_explorer_keep_the_risk_flag(owner, reviewer, access):
    flagged, version = services.create_risk(owner.user, access, title="Flagged", statement="s", owner_role="o",
                                            in_sox_scope=True)
    publish(version, reviewer.user)
    _, other = services.create_risk(owner.user, access, title="Unflagged", statement="s", owner_role="o")
    publish(other, reviewer.user)
    assert "SOX scope" in owner.get(flagged.get_absolute_url()).content.decode()
    html = owner.get(reverse("rcm:explorer"), {"sox": "1"}).content.decode()
    assert "Flagged" in html and "Unflagged" not in html


# Themes

def test_stage_and_theme_together_are_rejected(owner, access):
    theme = access.themes.first()
    stage = access.stages.first()
    for url, post in (
        (reverse("rcm:control_new"), control_post(access, stage, theme=theme.pk)),
        (reverse("rcm:risk_new"), risk_post(access, stage=stage.pk, theme=theme.pk)),
    ):
        response = owner.post(url, post)
        assert response.status_code == 200
        assert "Choose a stage or a theme, not both." in response.context["form"].errors["theme"]
    assert not Control.objects.exists() and not Risk.objects.exists()


def test_theme_must_belong_to_topic(owner, access, other_topic):
    foreign = other_topic.themes.first()
    response = owner.post(reverse("rcm:control_new"), control_post(access, theme=foreign.pk))
    assert response.status_code == 200
    assert "Pick a theme from the selected topic." in response.context["form"].errors["theme"]


def test_theme_is_saved_and_shown_on_forms(owner, access):
    theme = access.themes.get(name="Privileged access")
    owner.post(reverse("rcm:control_new"), control_post(access, theme=theme.pk))
    owner.post(reverse("rcm:risk_new"), risk_post(access, theme=theme.pk))
    assert ControlVersion.objects.get().theme == theme
    risk = Risk.objects.get()
    assert risk.versions.get().theme == theme
    html = owner.get(reverse("rcm:risk_edit", args=[risk.ident])).content.decode()
    assert "Use a theme instead of a stage when this applies across the whole lifecycle." in html
    assert f'<option value="{theme.pk}" selected>' in html


def test_topic_options_endpoint_is_signed_in_only(access):
    from django.test import Client

    assert Client().get(reverse("rcm:topic_options"), {"topic": access.pk}).status_code == 403


def test_detail_band_shows_theme_instead_of_stage(owner, reviewer, access):
    theme = access.themes.get(name="Privileged access")
    control, _ = published_control(access, owner.user, reviewer.user, theme=theme)
    html = owner.get(control.get_absolute_url()).content.decode()
    band = html.split('class="page-header"')[0]
    assert 'aria-current="page">Privileged access<' in band
    assert "lifecycle-strip" in band and 'aria-current="step"' not in band
    stage = access.stages.first()
    staged, _ = published_control(access, owner.user, reviewer.user, title="Staged", stage=stage)
    band = owner.get(staged.get_absolute_url()).content.decode().split('class="page-header"')[0]
    assert f'aria-current="step">{stage.name}<' in band


def test_explorer_row_shows_theme_name(owner, reviewer, access):
    theme = access.themes.get(name="Privileged access")
    published_control(access, owner.user, reviewer.user, theme=theme)
    assert f"{access.name} / Privileged access" in owner.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()


# Evidence rules

def make_rule(user, approver, name, applies_to, publish_it=True):
    entity, version = v.create_entity(
        EvidenceRule, EvidenceRuleVersion, user, {}, name=name, applies_to=applies_to, items=["An item"], position=0
    )
    if publish_it:
        publish(version, approver)
    return entity


def test_rule_applies_by_nature(owner, reviewer, access):
    detective = published_control(access, owner.user, reviewer.user, nature="detective")[1]
    preventive = published_control(access, owner.user, reviewer.user, title="P", nature="preventive")[1]
    for applies_to, d, p in (("all", True, True), ("detective", True, False), ("preventive", False, True)):
        rule = EvidenceRuleVersion(applies_to=applies_to)
        assert (rule_applies(rule, detective), rule_applies(rule, preventive)) == (d, p)


def test_control_page_lists_only_matching_rules(owner, reviewer, access):
    make_rule(owner.user, reviewer.user, "Rule for everyone", RuleAppliesTo.ALL)
    make_rule(owner.user, reviewer.user, "Review records", RuleAppliesTo.DETECTIVE)
    make_rule(owner.user, reviewer.user, "Prevent records", RuleAppliesTo.PREVENTIVE)
    detective, _ = published_control(access, owner.user, reviewer.user, nature="detective")
    preventive, _ = published_control(access, owner.user, reviewer.user, title="P", nature="preventive")
    page = owner.get(detective.get_absolute_url()).content.decode()
    assert "Rule for everyone" in page and "Review records" in page and "Prevent records" not in page
    page = owner.get(preventive.get_absolute_url()).content.decode()
    assert "Rule for everyone" in page and "Prevent records" in page and "Review records" not in page


def test_rule_form_has_applies_to(reviewer):
    html = reviewer.get(reverse("rcm:evidence_rule_new")).content.decode()
    assert "Applies to" in html and "Detective controls only" in html
    data = {"name": "R", "applies_to": "detective", "position": 0, "items": json.dumps(["x"])}
    reviewer.post(reverse("rcm:evidence_rule_new"), data)
    assert EvidenceRuleVersion.objects.get().applies_to == "detective"
    bad = reviewer.post(reverse("rcm:evidence_rule_new"), {**data, "name": "S", "applies_to": "nonsense"})
    assert bad.status_code == 200 and EvidenceRuleVersion.objects.count() == 1


# Seed command

def test_seed_evidence_rules_creates_drafts_once(reviewer):
    call_command("seed_evidence_rules", user="reviewer")
    versions = {r.name: r for r in EvidenceRuleVersion.objects.all()}
    assert set(versions) == {
        "Before you send evidence", "A complete review record", "Where evidence lives and how long it's kept",
    }
    assert all(r.status == v.Status.DRAFT and r.proposed_by == reviewer.user for r in versions.values())
    assert versions["A complete review record"].applies_to == "detective"
    assert versions["Before you send evidence"].applies_to == "all"
    assert len(versions["Where evidence lives and how long it's kept"].items) == 3
    call_command("seed_evidence_rules", user="reviewer")
    assert EvidenceRuleVersion.objects.count() == 3 and EvidenceRule.objects.count() == 3


def test_seed_skips_names_that_exist_in_any_version(reviewer, second_reviewer):
    make_rule(reviewer.user, second_reviewer.user, "Before you send evidence", RuleAppliesTo.ALL)
    call_command("seed_evidence_rules", user="reviewer")
    assert EvidenceRuleVersion.objects.count() == 3


def test_seed_needs_a_tech_risk_user(owner):
    outsider = As("outsider", "co")
    with pytest.raises(CommandError, match="Tech Risk"):
        call_command("seed_evidence_rules", user=outsider.username)
    with pytest.raises(CommandError, match="No user"):
        call_command("seed_evidence_rules", user="nobody")
    assert not EvidenceRuleVersion.objects.exists()


# Navigation

def active_nav(response):
    html = response.content.decode()
    nav = html.split('aria-label="Primary"')[1].split("</nav>")[0]
    return re.findall(r'aria-current="page">([^<]+)<', nav)


def test_every_rcm_page_highlights_risks_and_controls(owner, reviewer, access, live_control):
    risk, version = services.create_risk(owner.user, access, title="R", statement="s", owner_role="o")
    publish(version, reviewer.user)
    urls = [
        reverse("rcm:explorer"), live_control.get_absolute_url(), risk.get_absolute_url(),
        reverse("rcm:control_new"), reverse("rcm:risk_new"),
        reverse("rcm:evidence_rule_new"), reverse("rcm:control_edit", args=[live_control.ident]),
    ]
    for url in urls:
        assert active_nav(owner.get(url)) == ["Risks and controls"], url


def test_platform_pages_highlight_library(owner, topics):
    from apps.platforms.models import Platform

    call_command("seed_platforms")
    platform = Platform.objects.first()
    for url in (reverse("core:library"), platform.get_absolute_url()):
        assert active_nav(owner.get(url)) == ["Library"], url
