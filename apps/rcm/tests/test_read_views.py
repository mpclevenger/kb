"""Checks the pages people read: the explorer, and the control, risk and driver pages."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.roles import AUDITOR, CONTROL_OWNER, READ_ONLY, TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import control_fields, make_user
from apps.rcm import services
from apps.rcm.models import (
    Coverage,
    EvidenceRule,
    EvidenceRuleVersion,
)
from apps.topics.models import Topic

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def topics():
    call_command("seed_topics")


@pytest.fixture
def access():
    return Topic.objects.get(id_prefix="MA")


@pytest.fixture
def other_topic(access):
    return Topic.objects.exclude(pk=access.pk).first()


@pytest.fixture
def owner():
    return make_user("owner", TECH_RISK)


@pytest.fixture
def approver():
    return make_user("approver", TECH_RISK)


@pytest.fixture
def reader():
    return make_user("reader", READ_ONLY)


def publish(version, proposer, approver):
    v.submit(version, proposer)
    v.approve_and_publish(version, approver)
    return version


def make_control(topic, owner, approver, publish_it=True, **extra):
    entity, version = services.create_control(owner, topic, **control_fields(**extra))
    if publish_it:
        publish(version, owner, approver)
    return entity


def make_risk(topic, owner, approver, controls=(), publish_it=True, **extra):
    fields = dict(title="Leaver keeps access", statement="Access is not removed.", owner_role="IAM")
    fields.update(extra)
    entity, version = services.create_risk(owner, topic, **fields)
    services.set_risk_links(version, owner, controls=controls)
    if publish_it:
        publish(version, owner, approver)
    return entity


def as_role(client, settings, role, name="viewer"):
    settings.AUTH_MODE = "sso"
    settings.SSO_GROUP_ROLE_MAP = f"grp:{role}"
    client.defaults.update(HTTP_X_AUTH_USER=name, HTTP_X_AUTH_GROUPS="grp")
    return client


def as_user(client, settings, user, role):
    return as_role(client, settings, role, user.username)


@pytest.fixture
def register(access, owner, approver):
    key = make_control(access, owner, approver, title="Key review", level="key")
    minor = make_control(access, owner, approver, title="Minor check")
    loose = make_control(access, owner, approver, title="Orphan control")
    covered = make_risk(
        access, owner, approver, title="Covered risk",
        controls=[(key, Coverage.FULL, "Reviews all users")],
    )
    partial = make_risk(
        access, owner, approver, title="Partial risk",
        controls=[(minor, Coverage.PARTIAL, "Checks some users")],
    )
    unmapped = make_risk(access, owner, approver, title="Gap risk")
    return dict(key=key, minor=minor, loose=loose, covered=covered, partial=partial,
                unmapped=unmapped)


class TestExplorer:
    def test_empty_state(self, client):
        response = client.get(reverse("rcm:explorer"))
        assert response.status_code == 200
        assert b"Nothing published yet" in response.content

    def test_summary_counts_and_rows(self, client, register):
        html = client.get(reverse("rcm:explorer")).content.decode()
        for title in ("Covered risk", "Partial risk", "Gap risk"):
            assert title in html
        assert "Controls not linked to any risk" in html
        assert "Orphan control" in html
        ctx = client.get(reverse("rcm:explorer")).context
        assert ctx["summary"] == {"risks": 3, "controls": 3, "unmapped": 1, "unlinked": 1}

    def test_summary_tiles_use_type_and_alert_colors(self, client, register):
        html = client.get(reverse("rcm:explorer")).content.decode()
        assert '<div class="count-tile count-tile-risk"><dt>Risks</dt><dd>3</dd>' in html
        assert '<div class="count-tile count-tile-control"><dt>Controls</dt><dd>3</dd>' in html
        assert '<div class="count-tile count-tile-alert"><dt>Unmapped risks</dt><dd>1</dd>' in html
        assert '<div class="count-tile count-tile-neutral"><dt>Controls not linked to a risk</dt><dd>1</dd>' in html

    def test_unmapped_tile_is_neutral_when_every_risk_is_mapped(self, client, access, owner, approver):
        control = make_control(access, owner, approver, title="Key review")
        make_risk(access, owner, approver, title="Covered risk", controls=[(control, Coverage.FULL, "Reviews all")])
        html = client.get(reverse("rcm:explorer")).content.decode()
        assert '<div class="count-tile count-tile-neutral"><dt>Unmapped risks</dt><dd>0</dd>' in html

    def test_link_chips_show_a_colored_type_pill(self, client, register):
        html = client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
        assert '<span class="type-pill type-pill-risk">Risk</span>' in html

    def test_partial_marker(self, client, register):
        html = client.get(reverse("rcm:explorer")).content.decode()
        assert "trac-badge-coverage tone-partial" in html

    def test_filter_by_topic(self, client, register, access, other_topic):
        url = reverse("rcm:explorer")
        assert b"Covered risk" in client.get(url, {"topic": access.slug}).content
        none = client.get(url, {"topic": other_topic.slug}).content.decode()
        assert "Covered risk" not in none
        assert "No matches" in none

    def test_filter_by_stage_follows_topic(self, client, register, access):
        stage = access.stages.first()
        html = client.get(reverse("rcm:explorer"), {"topic": access.slug, "stage": stage.pk}).content.decode()
        assert "No matches" in html
        ignored = client.get(reverse("rcm:explorer"), {"stage": stage.pk}).content.decode()
        assert "Covered risk" in ignored

    @pytest.mark.parametrize(
        "coverage,present,absent",
        [
            ("covered", "Covered risk", "Partial risk"),
            ("partial", "Partial risk", "Covered risk"),
            ("unmapped", "Gap risk", "Covered risk"),
        ],
    )
    def test_filter_by_coverage(self, client, register, coverage, present, absent):
        html = client.get(reverse("rcm:explorer"), {"coverage": coverage}).content.decode()
        assert present in html
        assert absent not in html

    def test_key_only(self, client, register):
        html = client.get(reverse("rcm:explorer"), {"level": "key"}).content.decode()
        assert "Covered risk" in html
        assert "Key review" in html
        assert "Partial risk" not in html
        assert "Orphan control" not in html

    def test_level_filter(self, client, access, owner, approver):
        make_control(access, owner, approver, title="Top one", level="key")
        make_control(access, owner, approver, title="Helper one", level="supporting")
        html = client.get(reverse("rcm:explorer"), {"view": "controls", "level": "supporting"}).content.decode()
        assert "Helper one" in html
        assert "Top one" not in html

    def test_controls_view_is_sorted_by_level_and_not_folded(self, client, access, owner, approver):
        make_control(access, owner, approver, title="Aaa helper", level="supporting")
        make_control(access, owner, approver, title="Zzz top", level="key")
        make_control(access, owner, approver, title="Mmm plain", level="non-key")
        html = client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
        assert html.index("Zzz top") < html.index("Mmm plain") < html.index("Aaa helper")
        assert "More controls" not in html

    def test_text_search(self, client, register):
        html = client.get(reverse("rcm:explorer"), {"q": "partial"}).content.decode()
        assert "Partial risk" in html
        assert "Covered risk" not in html
        by_id = client.get(reverse("rcm:explorer"), {"q": register["covered"].ident}).content.decode()
        assert "Covered risk" in by_id

    def test_control_view(self, client, register):
        html = client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
        assert "Key review" in html and "Orphan control" in html
        assert "Not linked to any risk" in html
        assert "Controls not linked to any risk" not in html

    def test_htmx_returns_only_results(self, client, register):
        response = client.get(reverse("rcm:explorer"), {"level": "key"}, HTTP_HX_REQUEST="true")
        html = response.content.decode()
        assert "<html" not in html and "<form" not in html
        assert "Covered risk" in html
        assert 'hx-swap-oob="true"' in html
        assert "HX-Request" in response["Vary"]

    def test_full_page_has_filter_form_once(self, client, register):
        html = client.get(reverse("rcm:explorer")).content.decode()
        assert html.count('id="stage"') == 1
        assert 'hx-get="/rcm/"' in html

    def test_excludes_drafts_and_retired(self, client, access, owner, approver, register):
        make_risk(access, owner, approver, title="Draft risk", publish_it=False)
        retiring = register["unmapped"]
        retire = v.propose_retirement(retiring, owner, "No longer relevant")
        publish(retire, owner, approver)
        html = client.get(reverse("rcm:explorer")).content.decode()
        assert "Draft risk" not in html
        assert "Gap risk" not in html


class TestControlPage:
    def test_sections_render_in_order(self, client, register):
        response = client.get(register["key"].get_absolute_url())
        html = response.content.decode()
        order = ["Why this control exists", "Do I need this?", "What good looks like", "How to run it"]
        positions = [html.index(h) for h in order]
        assert positions == sorted(positions)
        for tone in ("why", "need", "good", "how"):
            assert f"section-card-{tone}" in html
        assert html.count("<details ") == 4 and "data-section-toolbar" in html
        assert "tone-preventive" in html or "tone-detective" in html
        assert "Addresses:" in html and "Covered risk" in html
        assert "This control applies if any of these are true." in html
        assert "that procedure is what reviewers test" in html
        assert "Keep:" in html and "Signed review" in html
        assert "tone-key" in html
        assert "Owner" in html

    def test_empty_sections_are_hidden(self, client, access, owner, approver):
        control = make_control(access, owner, approver, applies_when=[], criteria=[], steps=[])
        html = client.get(control.get_absolute_url()).content.decode()
        assert "Why this control exists" in html
        assert "Do I need this?" not in html
        assert "What good looks like" not in html
        assert "How to run it" not in html

    def test_evidence_rules_follow_criteria(self, client, access, owner, approver):
        rule, rule_version = v.create_entity(
            EvidenceRule, EvidenceRuleVersion, owner,
            name="Screenshots, every time", items=["Show the date and time."], position=1,
        )
        publish(rule_version, owner, approver)
        control = make_control(access, owner, approver)
        html = client.get(control.get_absolute_url()).content.decode()
        assert html.index("Every user has a decision.") < html.index("Screenshots, every time")
        assert "Show the date and time." in html

    def test_governance_footer(self, client, register):
        html = client.get(register["key"].get_absolute_url()).content.decode()
        assert "Version" in html and "Approver" in html and "Effective date" in html
        assert "approver" in html

    def test_unknown_control_404(self, client):
        assert client.get(reverse("rcm:control", args=["ZZ-99"])).status_code == 404


class TestHistoryLink:
    @pytest.mark.parametrize(
        "role,expected", [(TECH_RISK, True), (AUDITOR, True), (CONTROL_OWNER, False), (READ_ONLY, False)]
    )
    def test_history_link_by_role(self, client, settings, register, role, expected):
        as_role(client, settings, role)
        control = register["key"]
        html = client.get(control.get_absolute_url()).content.decode()
        history = reverse(
            "core:history", args=[ContentType.objects.get_for_model(control).pk, control.pk]
        )
        assert (history in html) is expected


class TestDraftVisibility:
    @pytest.fixture
    def draft(self, access, owner, approver):
        return make_control(access, owner, approver, publish_it=False, title="Brand new control")

    def test_read_only_gets_404(self, client, settings, draft):
        as_role(client, settings, READ_ONLY)
        assert client.get(draft.get_absolute_url()).status_code == 404

    def test_other_control_owner_gets_404(self, client, settings, draft):
        other = make_user("other", CONTROL_OWNER)
        as_user(client, settings, other, CONTROL_OWNER)
        assert client.get(draft.get_absolute_url()).status_code == 404

    def test_proposer_sees_banner(self, client, settings, draft, owner):
        as_user(client, settings, owner, TECH_RISK)
        response = client.get(draft.get_absolute_url())
        assert response.status_code == 200
        assert "Draft, not official" in response.content.decode()

    def test_tech_risk_sees_banner(self, client, draft):
        response = client.get(draft.get_absolute_url())
        assert response.status_code == 200
        assert "Draft, not official" in response.content.decode()

    def test_draft_not_in_explorer(self, client, draft):
        html = client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
        assert "Brand new control" not in html


class TestInReview:
    @pytest.fixture
    def reviewed(self, access, owner, approver):
        control = make_control(access, owner, approver)
        proposer = make_user("editor", TECH_RISK)
        draft = v.propose_change(control, proposer, "tweak", title="Edited title")
        v.submit(draft, proposer)
        return control, proposer, draft

    def test_notice_without_proposer_name_for_read_only(self, client, settings, reviewed):
        control, *_ = reviewed
        as_role(client, settings, READ_ONLY)
        response = client.get(control.get_absolute_url())
        html = response.content.decode()
        assert "An edit to this page is in review" in html
        assert "editor" not in html
        assert "?version=" not in html
        assert "Edited title" not in html
        assert "Draft, not official" not in html

    def test_tech_risk_sees_proposer_and_link(self, client, reviewed):
        control, _, draft = reviewed
        html = client.get(control.get_absolute_url()).content.decode()
        assert "An edit to this page is in review" in html
        assert "editor" in html
        assert f"?version={draft.number}" in html
        assert "Quarterly user access review" in html

    def test_version_param_shows_draft(self, client, reviewed):
        control, _, draft = reviewed
        html = client.get(control.get_absolute_url(), {"version": draft.number}).content.decode()
        assert "Draft, not official" in html
        assert "Edited title" in html

    def test_version_param_blocked_for_read_only(self, client, settings, reviewed):
        control, _, draft = reviewed
        as_role(client, settings, READ_ONLY)
        assert client.get(control.get_absolute_url(), {"version": draft.number}).status_code == 404

    def test_proposer_gets_link(self, client, settings, reviewed):
        control, proposer, draft = reviewed
        as_user(client, settings, proposer, TECH_RISK)
        html = client.get(control.get_absolute_url()).content.decode()
        assert f"?version={draft.number}" in html

    def test_bad_version_param(self, client, reviewed):
        control, *_ = reviewed
        assert client.get(control.get_absolute_url(), {"version": "abc"}).status_code == 404
        assert client.get(control.get_absolute_url(), {"version": "99"}).status_code == 404


class TestRetired:
    def test_retired_notice_and_still_reachable(self, client, access, owner, approver):
        control = make_control(access, owner, approver)
        retire = v.propose_retirement(control, owner, "Replaced by automation")
        publish(retire, owner, approver)
        response = client.get(control.get_absolute_url())
        assert response.status_code == 200
        html = response.content.decode()
        assert "Retired" in html
        assert "Replaced by automation" in html
        assert control.ident not in client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()


class TestRiskPages:
    def test_risk_page(self, client, register):
        html = client.get(register["covered"].get_absolute_url()).content.decode()
        assert "Access is not removed." in html
        assert "Key review" in html
        assert "Reviews all users" in html
        assert "Covered" in html

    def test_partial_risk_badge(self, client, register):
        html = client.get(register["partial"].get_absolute_url()).content.decode()
        assert "Checks some users" in html
        assert "Partial" in html

    def test_unmapped_risk_page(self, client, register):
        html = client.get(register["unmapped"].get_absolute_url()).content.decode()
        assert "Unmapped" in html
        assert "No control addresses this risk yet." in html

    def test_risk_draft_404_for_read_only(self, client, settings, access, owner, approver):
        risk = make_risk(access, owner, approver, publish_it=False)
        as_role(client, settings, READ_ONLY)
        assert client.get(risk.get_absolute_url()).status_code == 404


class TestExplorerVisibility:
    def test_drafts_are_left_out(self, client, register, access, owner, approver):
        make_control(access, owner, approver, publish_it=False, title="Hidden draft control")
        make_risk(access, owner, approver, publish_it=False, title="Hidden draft risk")
        risks = client.get(reverse("rcm:explorer")).content.decode()
        controls = client.get(reverse("rcm:explorer"), {"view": "controls"}).content.decode()
        assert "Covered risk" in risks and "Hidden draft risk" not in risks
        assert "Key review" in controls and "Hidden draft control" not in controls

    def test_requires_viewer_role(self, client, settings):
        settings.AUTH_MODE = "sso"
        response = client.get(reverse("rcm:explorer"))
        assert response.status_code == 403
