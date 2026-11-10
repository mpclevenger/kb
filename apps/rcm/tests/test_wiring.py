"""Checks that buttons, messages and links on the risk and control pages are connected correctly."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import Control, Risk
from apps.core.tests.support import As
from apps.topics.models import Topic

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


@pytest.fixture
def access():
    call_command("seed_topics")
    return Topic.objects.get(id_prefix="MA")


@pytest.fixture
def owner():
    return As("owner", "tr")


@pytest.fixture
def reviewer():
    return As("reviewer", "tr")


@pytest.fixture
def reader():
    return As("reader", "ro")


def control_fields(**extra):
    data = dict(title="Access review", why="Because.", owner_role="IAM", nature="detective", method="manual",
                frequency="monthly")
    data.update(extra)
    return data


def published_control(access, proposer, approver, **extra):
    entity, version = services.create_control(proposer.user, access, **control_fields(**extra))
    v.submit(version, proposer.user)
    v.approve_and_publish(version, approver.user)
    return entity


def published_risk(access, proposer, approver, **extra):
    fields = dict(title="Leaver keeps access", statement="Not removed.", owner_role="IAM")
    fields.update(extra)
    entity, version = services.create_risk(proposer.user, access, **fields)
    v.submit(version, proposer.user)
    v.approve_and_publish(version, approver.user)
    return entity


@pytest.fixture
def items(access, owner, reviewer):
    return {
        "control": published_control(access, owner, reviewer),
        "risk": published_risk(access, owner, reviewer),
    }


EDIT = {"control": "rcm:control_edit", "risk": "rcm:risk_edit"}


def edit_url(kind, entity):
    return reverse(EDIT[kind], args=[entity.ident])


class TestMessages:
    def test_workflow_message_renders_once_below_band(self, access, owner, reviewer):
        control = published_control(access, owner, reviewer)
        draft = v.propose_change(control, owner.user, "x", title="Other")
        next_url = control.get_absolute_url() + "?version=2"
        response = owner.post(
            reverse("workflow:submit", args=[_ctype(draft), draft.pk]), {"next": next_url}, follow=True
        )
        html = response.content.decode()
        assert html.count("Submitted for review") == 1
        assert 'class="trac-alert trac-alert-success' in html
        assert 'data-bs-dismiss="alert"' in html
        assert html.index("trac-alert-success") < html.index('class="page-header"')

    def test_message_is_consumed(self, access, owner, reviewer):
        control = published_control(access, owner, reviewer)
        draft = v.propose_change(control, owner.user, "x", title="Other")
        owner.post(reverse("workflow:submit", args=[_ctype(draft), draft.pk]), follow=True)
        assert "Submitted for review" not in owner.get(control.get_absolute_url()).content.decode()

    def test_error_message_uses_error_style(self, access, owner, reviewer):
        control = published_control(access, owner, reviewer)
        draft = v.propose_change(control, owner.user, "x", title="Other")
        response = owner.post(
            reverse("workflow:withdraw", args=[_ctype(draft), draft.pk]),
            {"next": control.get_absolute_url() + "?version=2"}, follow=True,
        )
        html = response.content.decode()
        assert html.count("Only items in review can be withdrawn.") == 1
        assert "trac-alert-error" in html

    def test_form_page_renders_message_once(self, access, owner, reviewer):
        control = published_control(access, owner, reviewer)
        draft = v.propose_change(control, owner.user, "x", title="Other")
        v.submit(draft, owner.user)
        v.withdraw(draft, owner.user)
        response = owner.get(edit_url("control", control))
        assert response.status_code == 200
        owner.post(reverse("workflow:discard", args=[_ctype(draft), draft.pk]))
        response = owner.get(edit_url("control", control))
        assert response.content.decode().count("Draft discarded") == 1


def _ctype(version):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(version).pk


class TestFooter:
    def test_review_by_shown(self, access, owner, reviewer):
        future = timezone.localdate() + timedelta(days=30)
        control = published_control(access, owner, reviewer, review_by=future)
        html = owner.get(control.get_absolute_url()).content.decode()
        assert "Review by" in html
        assert "Overdue" not in html

    def test_overdue_when_past(self, access, owner, reviewer):
        past = timezone.localdate() - timedelta(days=3)
        control = published_control(access, owner, reviewer, review_by=past)
        html = owner.get(control.get_absolute_url()).content.decode()
        assert "Review by" in html and "Overdue" in html

    def test_hidden_when_empty(self, items, owner):
        for entity in items.values():
            assert "Review by" not in owner.get(entity.get_absolute_url()).content.decode()

    def test_risk_review_by(self, access, owner, reviewer):
        past = timezone.localdate() - timedelta(days=1)
        risk = published_risk(access, owner, reviewer, review_by=past)
        html = owner.get(risk.get_absolute_url()).content.decode()
        assert "Review by" in html and "Overdue" in html


class TestProposeButton:
    @pytest.mark.parametrize("kind", ["control", "risk"])
    def test_visible_for_tech_risk_only(self, kind, items, owner, reader):
        html = owner.get(items[kind].get_absolute_url()).content.decode()
        assert "Propose a change" in html
        assert f'href="{edit_url(kind, items[kind])}"' in html
        assert "Propose a change" not in reader.get(items[kind].get_absolute_url()).content.decode()

    def test_hidden_for_anonymous(self, items):
        from django.test import Client

        response = Client().get(items["control"].get_absolute_url())
        assert "Propose a change" not in response.content.decode()

    @pytest.mark.parametrize("kind", ["control", "risk"])
    def test_hidden_with_open_proposal_and_notice_shown(self, kind, items, owner, reviewer):
        entity = items[kind]
        draft = v.propose_change(entity, owner.user, "x", title="Other")
        v.submit(draft, owner.user)
        html = reviewer.get(entity.get_absolute_url()).content.decode()
        assert "Propose a change" not in html
        assert "An edit to this page is in review" in html

    def test_hidden_on_draft_view(self, access, owner):
        entity, version = services.create_control(owner.user, access, **control_fields())
        html = owner.get(entity.get_absolute_url() + "?version=1").content.decode()
        assert "Propose a change" not in html

    def test_hidden_when_retired(self, items, owner, reviewer):
        control = items["control"]
        retire = v.propose_retirement(control, owner.user, "gone")
        v.submit(retire, owner.user)
        v.approve_and_publish(retire, reviewer.user)
        assert "Propose a change" not in owner.get(control.get_absolute_url()).content.decode()


class TestWorkflowOnDetail:
    def test_proposer_sees_submit_and_discard(self, access, owner):
        entity, _ = services.create_control(owner.user, access, **control_fields())
        html = owner.get(entity.get_absolute_url() + "?version=1").content.decode()
        assert "Submit for review" in html and "Discard draft" in html
        assert "Approve and publish" not in html

    def test_tech_risk_sees_draft_without_actions(self, access, owner, reviewer):
        entity, _ = services.create_control(owner.user, access, **control_fields())
        html = reviewer.get(entity.get_absolute_url() + "?version=1").content.decode()
        assert "Submit for review" not in html and "Approve and publish" not in html

    def test_in_review_proposer_withdraws_approver_decides(self, access, owner, reviewer):
        entity, version = services.create_control(owner.user, access, **control_fields())
        v.submit(version, owner.user)
        url = entity.get_absolute_url() + "?version=1"
        owner_html = owner.get(url).content.decode()
        assert "Withdraw" in owner_html and "Approve and publish" not in owner_html
        reviewer_html = reviewer.get(url).content.decode()
        assert "Approve and publish" in reviewer_html and "Reject" in reviewer_html
        assert "Withdraw" not in reviewer_html

    def test_reader_cannot_see_draft(self, access, owner, reader):
        entity, _ = services.create_control(owner.user, access, **control_fields())
        assert reader.get(entity.get_absolute_url() + "?version=1").status_code == 404

    def test_workflow_on_risk_draft(self, access, owner):
        risk, _ = services.create_risk(owner.user, access, title="R", statement="S", owner_role="IAM")
        html = owner.get(risk.get_absolute_url() + "?version=1").content.decode()
        assert "Submit for review" in html

    def test_not_shown_on_published_page(self, items, owner):
        html = owner.get(items["control"].get_absolute_url()).content.decode()
        assert "Submit for review" not in html


class TestNewButtons:
    def test_explorer_has_both(self, items, owner):
        html = owner.get(reverse("rcm:explorer")).content.decode()
        for label, target in (("New control", "rcm:control_new"), ("New risk", "rcm:risk_new")):
            assert label in html and f'href="{reverse(target)}"' in html
        assert "New driver" not in html

    def test_explorer_empty_state_still_has_buttons(self, owner):
        html = owner.get(reverse("rcm:explorer")).content.decode()
        assert "New control" in html

    def test_explorer_and_its_buttons_are_closed_to_non_tech_risk(self, items, reader):
        assert reader.get(reverse("rcm:explorer")).status_code == 403
        for target in ("rcm:control_new", "rcm:risk_new"):
            assert reader.get(reverse(target)).status_code == 403

    def test_hidden_for_anonymous(self, items):
        from django.test import Client

        response = Client().get(reverse("rcm:explorer"))
        assert "New control" not in response.content.decode()


class TestDiscardRedirect:
    def test_first_control_draft_goes_to_control_view(self, access, owner):
        entity, version = services.create_control(owner.user, access, **control_fields())
        response = owner.post(reverse("workflow:discard", args=[_ctype(version), version.pk]))
        assert response.status_code == 302 and response.url == f"{reverse('rcm:explorer')}?view=controls"
        assert not Control.objects.filter(pk=entity.pk).exists()

    def test_first_risk_draft_goes_to_explorer(self, access, owner):
        entity, version = services.create_risk(owner.user, access, title="R", statement="S", owner_role="IAM")
        response = owner.post(reverse("workflow:discard", args=[_ctype(version), version.pk]))
        assert response.status_code == 302 and response.url == reverse("rcm:explorer")
        assert not Risk.objects.filter(pk=entity.pk).exists()


def test_proposer_sees_edit_draft_link_on_own_draft(access, owner, reader):
    control, _ = services.create_control(owner.user, access, **control_fields())
    url = control.get_absolute_url() + "?version=1"
    edit = reverse("rcm:control_edit", args=[control.ident])
    assert edit in owner.get(url).content.decode()
    assert reader.get(url).status_code == 404


def test_hidden_draft_announced_without_details(access, owner, reader, reviewer):
    control = published_control(access, owner, reviewer)
    v.propose_change(control, owner.user, "Reword", title="New")
    body = reader.get(control.get_absolute_url()).content.decode()
    assert "Someone is preparing an edit to this page." in body
    assert "?version=2" not in body
    assert "Propose a change" not in body
