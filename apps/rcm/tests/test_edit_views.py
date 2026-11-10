"""Checks the create and edit forms for controls, risks and drivers."""

import html as htmllib
import json

import pytest
from django.urls import reverse

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import (
    Control,
    EvidenceRule,
    EvidenceRuleVersion,
    Risk,
)
from apps.core.tests.support import As, anonymous, control_post, publish, published_control, risk_post

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

# Control form

def test_new_control_form_renders(owner, access):
    response = owner.get(reverse("rcm:control_new"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Do I need this?" in html and "What good looks like" in html and "How to run it" in html
    assert 'hx-get="' + reverse("rcm:topic_options") + '"' in html
    for label in ("Theme", "Owner role", "Performed by (role)", "Reviewed by (role)", "References"):
        assert label in html
    assert "Use a theme instead of a stage when this applies across the whole lifecycle." in html
    assert "In SOX scope" not in html
    assert "Your change" not in html


def test_create_control_serializes_rows(owner, access):
    stage = access.stages.first()
    response = owner.post(reverse("rcm:control_new"), control_post(access, stage, level="key"))
    control = Control.objects.get()
    assert response.status_code == 302
    assert response.url == f"{control.get_absolute_url()}?version=1"
    version = control.versions.get()
    assert version.status == v.Status.DRAFT
    assert version.proposed_by == owner.user
    assert version.stage == stage and version.level == "key"
    assert version.applies_when == ["You approve access"]
    assert version.criteria == [{"name": "The review", "items": ["Every user has a decision."]}]
    assert version.steps == [{"role": "Owner", "text": "Review the list.", "evidence": "Signed review"}]
    assert control.ident == "T-C-001" or control.ident.startswith("T-C-")  # the ID typed on the form


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("criteria", [{"name": "", "items": ["x"]}], "Group 1: give the group a name."),
        ("criteria", [{"name": "Review", "items": [" "]}], "add at least one item"),
        ("steps", [{"role": "Owner", "text": "", "evidence": "proof"}], "Step 1: say what to do."),
        ("criteria", {"name": "x"}, "Something went wrong with this section"),
        ("criteria", [{"name": "x", "items": "not a list"}], "Something went wrong with this section"),
        ("steps", ["just text"], "Something went wrong with this section"),
        ("applies_when", [1, 2], "Something went wrong with this section"),
        ("applies_when", "not json at all", "Something went wrong with this section"),
    ],
)
def test_invalid_row_shapes_are_rejected_and_rows_are_kept(owner, access, field, value, message):
    raw = value if isinstance(value, str) else json.dumps(value)
    data = control_post(access, title="Keep this title", **{field: raw})
    response = owner.post(reverse("rcm:control_new"), data)
    assert response.status_code == 200
    assert not Control.objects.exists()
    html = response.content.decode()
    assert message in html
    assert "Keep this title" in html
    assert "is-invalid" in html or "invalid-feedback" in html
    form = response.context["form"]
    assert form[field].value() == raw
    assert 'data-rows-output' in html


def test_other_fields_are_validated_and_kept(owner, access):
    response = owner.post(reverse("rcm:control_new"), control_post(access, title="", nature="", owner_role="Kept owner"))
    assert response.status_code == 200
    assert not Control.objects.exists()
    form = response.context["form"]
    assert "title" in form.errors and "nature" in form.errors
    assert "Kept owner" in response.content.decode()


def test_stage_must_belong_to_topic(owner, access, other_topic):
    foreign = other_topic.stages.first()
    response = owner.post(reverse("rcm:control_new"), control_post(access, foreign))
    assert response.status_code == 200
    assert "Pick a stage from the selected topic." in response.content.decode()
    assert not Control.objects.exists()


def test_topic_options_lists_stages_and_themes_of_the_topic(owner, access, other_topic):
    html = owner.get(reverse("rcm:topic_options"), {"topic": access.pk}).content.decode()
    assert html.startswith('<option value="">No specific stage</option>')
    assert '<select id="id_theme" hx-swap-oob="innerHTML"><option value="">No theme</option>' in html
    for stage in access.stages.all():
        assert f'<option value="{stage.pk}">{stage.name}</option>' in html
    for theme in access.themes.all():
        assert f'<option value="{theme.pk}">{theme.name}</option>' in html
    assert f'value="{other_topic.stages.first().pk}"' not in html
    assert f'value="{other_topic.themes.first().pk}"' not in html
    empty = owner.get(reverse("rcm:topic_options"), {"topic": "nonsense"}).content.decode()
    assert empty == (
        '<option value="">No specific stage</option>'
        '<select id="id_theme" hx-swap-oob="innerHTML"><option value="">No theme</option></select>'
    )


def test_edit_form_shows_stage_choices_for_current_topic(owner, reviewer, access, other_topic):
    _, version = published_control(access, owner.user, reviewer.user, stage=access.stages.first())
    response = reviewer.get(reverse("rcm:control_edit", args=[version.entity.ident]))
    html = response.content.decode()
    for stage in access.stages.all():
        assert f'value="{stage.pk}"' in html
    assert f'value="{other_topic.stages.first().pk}"' not in html
    assert "Your change" in html


def test_edit_published_creates_v2_draft_copying_content(owner, reviewer, access):
    control, v1 = published_control(access, owner.user, reviewer.user, level="key")
    url = reverse("rcm:control_edit", args=[control.ident])
    form = reviewer.get(url).context["form"]
    assert form["title"].value() == "Existing control"
    assert json.loads(form["criteria"].value()) == [{"name": "A", "items": ["one"]}]

    post = control_post(access, title="Changed title", level="key", change_summary="Sharper title")
    response = owner.post(url, post)
    assert response.status_code == 302 and response.url == f"{control.get_absolute_url()}?version=2"
    v2 = control.versions.get(number=2)
    assert v2.status == v.Status.DRAFT and v2.proposed_by == owner.user
    assert v2.title == "Changed title" and v2.change_summary == "Sharper title"
    assert v2.steps == [{"role": "Owner", "text": "Review the list.", "evidence": "Signed review"}]
    v1.refresh_from_db()
    assert v1.title == "Existing control" and v1.status == v.Status.PUBLISHED


def test_edit_requires_change_summary(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    response = owner.post(reverse("rcm:control_edit", args=[control.ident]), control_post(access))
    assert response.status_code == 200
    assert "change_summary" in response.context["form"].errors
    assert control.versions.count() == 1


def test_edit_own_draft_updates_in_place(owner, access):
    owner.post(reverse("rcm:control_new"), control_post(access))
    control = Control.objects.get()
    url = reverse("rcm:control_edit", args=[control.ident])
    page = owner.get(url)
    assert page.status_code == 200 and "Your change" not in page.content.decode()
    owner.post(url, control_post(access, title="Second pass"))
    assert control.versions.count() == 1
    assert control.versions.get().title == "Second pass"


def test_editing_someone_elses_draft_is_blocked(owner, reviewer, access):
    owner.post(reverse("rcm:control_new"), control_post(access))
    control = Control.objects.get()
    url = reverse("rcm:control_edit", args=[control.ident])
    page = reviewer.get(url)
    assert page.status_code == 200
    assert "Someone else is already working on a change" in page.content.decode()
    assert "Save draft" not in page.content.decode()
    response = reviewer.post(url, control_post(access, title="Hijack"))
    assert response.status_code == 200
    assert "Someone else is already working" in response.content.decode()
    assert control.versions.get().title == "Quarterly review of user access"


def test_open_proposal_shows_friendly_message_instead_of_form(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    v.propose_change(control, reviewer.user, "Mine", title="Reviewer change")
    page = owner.get(reverse("rcm:control_edit", args=[control.ident]))
    html = page.content.decode()
    assert page.status_code == 200
    assert "Someone else is already working on a change to" in html
    assert "Save draft" not in html
    assert "Reviewer change" not in html
    assert "?version=2" in html
    mine = reviewer.get(reverse("rcm:control_edit", args=[control.ident]))
    assert "Save draft" in mine.content.decode()


def test_in_review_change_by_me_tells_me_to_withdraw(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    draft = v.propose_change(control, owner.user, "x", title="Mine")
    v.submit(draft, owner.user)
    html = owner.get(reverse("rcm:control_edit", args=[control.ident])).content.decode()
    assert "is in review" in html and "Withdraw" in html
    assert "?version=2" in html


def test_retired_control_cannot_be_edited(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    retire = v.propose_retirement(control, owner.user, "No longer needed")
    publish(retire, reviewer.user)
    html = owner.get(reverse("rcm:control_edit", args=[control.ident])).content.decode()
    assert "is retired" in html and "Save draft" not in html


# Permissions

@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_only_tech_risk_can_create_or_propose(owner, reviewer, access, group):
    control, _ = published_control(access, owner.user, reviewer.user)
    outsider = As("outsider", group)
    for name in ("control_new", "risk_new", "evidence_rule_new"):
        assert outsider.get(reverse(f"rcm:{name}")).status_code == 403
    assert outsider.post(reverse("rcm:control_new"), control_post(access)).status_code == 403
    edit = reverse("rcm:control_edit", args=[control.ident])
    assert outsider.get(edit).status_code == 403
    assert outsider.post(edit, control_post(access, change_summary="x")).status_code == 403
    assert Control.objects.count() == 1 and control.versions.count() == 1


def test_anonymous_gets_403_on_every_edit_page(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    urls = [
        reverse("rcm:control_new"),
        reverse("rcm:control_edit", args=[control.ident]),
        reverse("rcm:risk_new"),
        reverse("rcm:evidence_rule_new"),
        reverse("rcm:topic_options"),
    ]
    for url in urls:
        assert anonymous().get(url).status_code == 403
    assert anonymous().post(reverse("rcm:control_new"), control_post(access)).status_code == 403
    assert Control.objects.count() == 1


# Risks

def test_new_risk_form_lists_only_published_controls(owner, reviewer, access, live_control):
    services.create_control(
        owner.user,
        access,
        title="Draft only",
        why="x",
        owner_role="o",
        nature="detective",
        method="manual",
        frequency="daily",
    )
    html = owner.get(reverse("rcm:risk_new")).content.decode()
    assert f"{live_control.ident} Review access" in html
    assert "Draft only" not in html


def test_create_risk_with_links(owner, access, live_control):
    links = [{"control": live_control.ident, "coverage": "partial", "rationale": "Only covers leavers"}]
    response = owner.post(
        reverse("rcm:risk_new"),
        risk_post(access, controls=json.dumps(links), in_sox_scope="on"),
    )
    risk = Risk.objects.get()
    assert response.status_code == 302 and response.url == f"{risk.get_absolute_url()}?version=1"
    version = risk.versions.get()
    assert version.status == v.Status.DRAFT and version.in_sox_scope
    link = version.control_links.get()
    assert (link.control, link.coverage, link.rationale) == (live_control, "partial", "Only covers leavers")


@pytest.mark.parametrize(
    "rows,message",
    [
        ([{"control": "", "coverage": "full", "rationale": "why"}], "pick a control"),
        ([{"control": "MA-01", "coverage": "full", "rationale": ""}], "say why it covers this risk"),
        ([{"control": "NOPE-99", "coverage": "full", "rationale": "why"}], "isn't a published control"),
        ([{"control": "MA-01", "coverage": "most", "rationale": "why"}], "choose full or partial"),
        (
            [
                {"control": "MA-01", "coverage": "full", "rationale": "a"},
                {"control": "MA-01", "coverage": "partial", "rationale": "b"},
            ],
            "already linked above",
        ),
        ("{}", "Something went wrong with this section"),
    ],
)
def test_risk_link_rows_are_validated_and_kept(owner, access, live_control, rows, message):
    assert live_control.ident == "MA-01"
    raw = rows if isinstance(rows, str) else json.dumps(rows)
    response = owner.post(reverse("rcm:risk_new"), risk_post(access, controls=raw, title="Kept risk title"))
    assert response.status_code == 200
    assert message in htmllib.unescape(response.content.decode())
    assert "Kept risk title" in response.content.decode()
    assert response.context["form"]["controls"].value() == raw
    assert not Risk.objects.exists()


def test_unpublished_and_retired_controls_cannot_be_linked(owner, reviewer, access):
    _, draft = services.create_control(
        owner.user, access, title="Draft", why="x", owner_role="o", nature="detective", method="manual", frequency="daily"
    )
    retired, _ = published_control(access, owner.user, reviewer.user)
    publish(v.propose_retirement(retired, owner.user, "Gone"), reviewer.user)
    for ident in (draft.entity.ident, retired.ident):
        rows = json.dumps([{"control": ident, "coverage": "full", "rationale": "why"}])
        response = owner.post(reverse("rcm:risk_new"), risk_post(access, controls=rows))
        assert response.status_code == 200
        assert "isn't a published control" in htmllib.unescape(response.content.decode())
    assert not Risk.objects.exists()


def test_edit_published_risk_copies_links_into_v2_draft(owner, reviewer, access, live_control):
    links = [{"control": live_control.ident, "coverage": "full", "rationale": "Covers it"}]
    owner.post(reverse("rcm:risk_new"), risk_post(access, controls=json.dumps(links)))
    risk = Risk.objects.get()
    publish(risk.versions.get(), reviewer.user)

    url = reverse("rcm:risk_edit", args=[risk.ident])
    form = owner.get(url).context["form"]
    assert json.loads(form["controls"].value()) == links

    response = owner.post(
        url,
        risk_post(
            access,
            title="Sharper title",
            controls=json.dumps(links),
            change_summary="Retitled",
        ),
    )
    assert response.status_code == 302 and response.url.endswith("?version=2")
    v2 = risk.versions.get(number=2)
    assert v2.status == v.Status.DRAFT and v2.title == "Sharper title"
    assert [(l.control, l.coverage, l.rationale) for l in v2.control_links.all()] == [
        (live_control, "full", "Covers it")
    ]
    assert risk.versions.get(number=1).control_links.count() == 1


def test_edit_risk_draft_replaces_links(owner, access, live_control):
    rows = json.dumps([{"control": live_control.ident, "coverage": "full", "rationale": "first"}])
    owner.post(reverse("rcm:risk_new"), risk_post(access, controls=rows))
    risk = Risk.objects.get()
    owner.post(reverse("rcm:risk_edit", args=[risk.ident]), risk_post(access, controls="[]"))
    assert risk.versions.count() == 1
    assert risk.versions.get().control_links.count() == 0


# Evidence rules

def test_evidence_rule_is_tech_risk_only(reviewer):
    owner = As("owner", "co")
    data = {"name": "Screenshots", "applies_to": "all", "position": 1, "items": json.dumps(["Shows the date", "", "Shows the user"])}
    assert owner.get(reverse("rcm:evidence_rule_new")).status_code == 403
    assert owner.post(reverse("rcm:evidence_rule_new"), data).status_code == 403
    assert not EvidenceRule.objects.exists()

    response = reviewer.post(reverse("rcm:evidence_rule_new"), data)
    rule = EvidenceRule.objects.get()
    assert response.status_code == 302 and response.url.startswith(reverse("rcm:evidence_rule_edit", args=[rule.pk]))
    version = rule.versions.get()
    assert version.items == ["Shows the date", "Shows the user"] and version.position == 1
    assert version.status == v.Status.DRAFT

    page = reviewer.get(response.url)
    assert "Submit for review" in page.content.decode()
    assert owner.get(response.url).status_code == 403


def test_evidence_rule_needs_items(reviewer):
    response = reviewer.post(reverse("rcm:evidence_rule_new"), {"name": "Empty", "applies_to": "all", "position": 0, "items": "[]"})
    assert response.status_code == 200
    assert "Add at least one item." in response.content.decode()
    assert not EvidenceRule.objects.exists()


def test_edit_published_evidence_rule(reviewer, second_reviewer):
    rule, version = v.create_entity(
        EvidenceRule, EvidenceRuleVersion, reviewer.user, {}, name="Screenshots", items=["a"], position=0
    )
    publish(version, second_reviewer.user)
    url = reverse("rcm:evidence_rule_edit", args=[rule.pk])
    data = {"name": "Screenshots", "applies_to": "all", "position": 2, "items": json.dumps(["a", "b"]), "change_summary": "Added b"}
    assert reviewer.post(url, data).status_code == 302
    v2 = rule.versions.get(number=2)
    assert v2.items == ["a", "b"] and v2.position == 2 and v2.status == v.Status.DRAFT
