"""Checks that the Submit, Approve, Reject and Withdraw buttons appear for, and work for, the right people."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import Control, ControlVersion
from apps.core.tests.support import As, anonymous
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
def reader():
    return As("reader", "ro")


@pytest.fixture
def reviewer():
    return As("reviewer", "tr")


@pytest.fixture
def second_reviewer():
    return As("reviewer2", "tr")


def draft_by(who, topic, **extra):
    _, version = services.create_control(
        who.user,
        topic,
        title="Access review",
        why="Because.",
        owner_role="IAM",
        nature="detective",
        method="manual",
        frequency="monthly",
        **extra,
    )
    return version


def url(action, version):
    return reverse(f"workflow:{action}", args=[ContentType.objects.get_for_model(version).pk, version.pk])


def buttons(version, who):
    request = RequestFactory().get(f"/rcm/controls/{version.entity.ident}/")
    request.user = who.user
    html = render_to_string("core/workflow_actions.html", {"version": version, "request": request})
    names = {
        "submit": "Submit for review",
        "discard": "Discard draft",
        "withdraw": "Withdraw",
        "approve": "Approve and publish",
        "reject": "Reject",
    }
    return {key for key, label in names.items() if f">{label}<" in html}


# Which buttons each person sees

def test_draft_buttons_only_for_proposer(access, owner, reviewer):
    version = draft_by(owner, access)
    assert buttons(version, owner) == {"submit", "discard"}
    assert buttons(version, reviewer) == set()


def test_in_review_buttons(access, owner, reviewer, second_reviewer, reader):
    version = draft_by(owner, access)
    v.submit(version, owner.user)
    assert buttons(version, owner) == {"withdraw"}
    assert buttons(version, reviewer) == {"approve", "reject"}
    assert buttons(version, reader) == set()


def test_tech_risk_proposer_cannot_approve_own_change(access, reviewer, second_reviewer):
    version = draft_by(reviewer, access)
    v.submit(version, reviewer.user)
    assert buttons(version, reviewer) == {"withdraw"}
    assert buttons(version, second_reviewer) == {"approve", "reject"}
    request = RequestFactory().get("/")
    request.user = reviewer.user
    html = render_to_string("core/workflow_actions.html", {"version": version, "request": request})
    assert "another member of Tech Risk" in html


def test_no_buttons_once_published_or_rejected(access, owner, reviewer):
    version = draft_by(owner, access)
    v.submit(version, owner.user)
    v.reject(version, reviewer.user, "No")
    assert buttons(version, owner) == set() and buttons(version, reviewer) == set()
    other = draft_by(owner, access)
    v.submit(other, owner.user)
    v.approve_and_publish(other, reviewer.user)
    assert buttons(other, owner) == set() and buttons(other, reviewer) == set()


def test_reject_form_requires_a_comment(access, owner, reviewer):
    version = draft_by(owner, access)
    v.submit(version, owner.user)
    request = RequestFactory().get("/")
    request.user = reviewer.user
    html = render_to_string("core/workflow_actions.html", {"version": version, "request": request})
    reject_form = html.split(url("reject", version))[1].split("</form>")[0]
    assert "<textarea" in reject_form and " required" in reject_form


# Flow through the views

def test_submit_then_approve_and_publish(access, owner, reviewer):
    version = draft_by(owner, access)
    entity = version.entity

    response = owner.post(url("submit", version))
    assert response.status_code == 302
    assert response.url == f"{entity.get_absolute_url()}?version=1"
    version.refresh_from_db()
    assert version.status == v.Status.IN_REVIEW

    response = reviewer.post(url("approve", version), {"comment": "Looks good"})
    assert response.status_code == 302 and response.url == entity.get_absolute_url()
    version.refresh_from_db()
    assert version.status == v.Status.PUBLISHED
    assert version.decided_by == reviewer.user and version.decision_comment == "Looks good"
    assert version.effective_from <= timezone.now()
    assert entity.current() == version


def test_messages_are_shown_after_each_step(access, owner, reviewer):
    version = draft_by(owner, access)
    response = owner.post(url("submit", version), follow=True)
    assert "Submitted for review" in [str(m) for m in response.context["messages"]]
    response = owner.post(url("withdraw", version), follow=True)
    assert "Withdrawn" in [str(m) for m in response.context["messages"]]
    owner.post(url("submit", version))
    response = reviewer.post(url("approve", version), follow=True)
    assert "Approved and published" in [str(m) for m in response.context["messages"]]


def test_reject_flow_and_comment_required(access, owner, reviewer):
    version = draft_by(owner, access)
    owner.post(url("submit", version))

    response = reviewer.post(url("reject", version), {"comment": "   "}, follow=True)
    version.refresh_from_db()
    assert version.status == v.Status.IN_REVIEW
    assert "A comment is required to reject." in [str(m) for m in response.context["messages"]]

    response = reviewer.post(url("reject", version), {"comment": "Needs owner sign-off"})
    version.refresh_from_db()
    assert version.status == v.Status.REJECTED
    assert version.decision_comment == "Needs owner sign-off"
    assert response.url == f"{version.entity.get_absolute_url()}?version=1"


def test_self_approval_is_forbidden(access, reviewer):
    version = draft_by(reviewer, access)
    reviewer.post(url("submit", version))
    assert reviewer.post(url("approve", version)).status_code == 403
    assert reviewer.post(url("reject", version), {"comment": "x"}).status_code == 403
    version.refresh_from_db()
    assert version.status == v.Status.IN_REVIEW


def test_non_approver_cannot_approve(access, owner, reader):
    version = draft_by(owner, access)
    owner.post(url("submit", version))
    assert reader.post(url("approve", version)).status_code in (403, 404)
    assert owner.post(url("approve", version)).status_code == 403
    version.refresh_from_db()
    assert version.status == v.Status.IN_REVIEW


def test_only_proposer_can_submit_withdraw_or_discard(access, owner, reviewer):
    version = draft_by(owner, access)
    assert reviewer.post(url("submit", version)).status_code == 403
    assert reviewer.post(url("discard", version)).status_code == 403
    owner.post(url("submit", version))
    assert reviewer.post(url("withdraw", version)).status_code == 403


def test_invisible_draft_is_404_for_others(access, owner, reader):
    version = draft_by(owner, access)
    assert reader.post(url("submit", version)).status_code == 404


def test_wrong_state_shows_message_and_redirects(access, owner):
    version = draft_by(owner, access)
    response = owner.post(url("withdraw", version), follow=True)
    assert "Only items in review can be withdrawn." in [str(m) for m in response.context["messages"]]
    version.refresh_from_db()
    assert version.status == v.Status.DRAFT


def test_get_is_not_allowed(access, owner):
    version = draft_by(owner, access)
    assert owner.get(url("submit", version)).status_code == 405


def test_anonymous_is_forbidden(access, owner):
    version = draft_by(owner, access)
    assert anonymous().post(url("submit", version)).status_code == 403


def test_non_governed_content_type_is_404(owner):
    user_ct = ContentType.objects.get(app_label="auth", model="user").pk
    response = owner.post(reverse("workflow:submit", args=[user_ct, 1]))
    assert response.status_code == 404


# next handling

@pytest.mark.parametrize(
    "target",
    ["https://evil.example/x", "//evil.example/x", "http://testserver.evil.example/", "javascript:alert(1)", "/\\evil.example"],
)
def test_next_ignores_other_hosts(access, owner, target):
    version = draft_by(owner, access)
    response = owner.post(url("submit", version), {"next": target})
    assert response.status_code == 302
    assert response.url == f"{version.entity.get_absolute_url()}?version=1"


def test_next_same_host_path_is_used(access, owner):
    version = draft_by(owner, access)
    response = owner.post(url("submit", version), {"next": "/rcm/?page=2"})
    assert response.url == "/rcm/?page=2"


# Approval dates

def test_approve_with_future_start_date(access, owner, reviewer):
    version = draft_by(owner, access)
    owner.post(url("submit", version))
    start = timezone.localdate() + timedelta(days=10)
    reviewer.post(url("approve", version), {"effective_date": start.isoformat()})
    version.refresh_from_db()
    assert version.status == v.Status.PUBLISHED
    local = timezone.localtime(version.effective_from)
    assert local.date() == start and (local.hour, local.minute) == (0, 0)
    assert version.entity.current() is None


@pytest.mark.parametrize("raw,message", [("2001-01-01", "can't be in the past"), ("soon", "year-month-day")])
def test_bad_start_date_is_rejected_without_publishing(access, owner, reviewer, raw, message):
    version = draft_by(owner, access)
    owner.post(url("submit", version))
    response = reviewer.post(url("approve", version), {"effective_date": raw}, follow=True)
    assert any(message in str(m) for m in response.context["messages"])
    version.refresh_from_db()
    assert version.status == v.Status.IN_REVIEW


def test_today_as_start_date_publishes_now(access, owner, reviewer):
    version = draft_by(owner, access)
    owner.post(url("submit", version))
    reviewer.post(url("approve", version), {"effective_date": timezone.localdate().isoformat()})
    version.refresh_from_db()
    assert version.entity.current() == version


# Discarding

def test_discard_first_draft_removes_item_and_goes_to_explorer(access, owner):
    version = draft_by(owner, access)
    response = owner.post(url("discard", version), {"next": f"/rcm/controls/{version.entity.ident}/?version=1"})
    assert response.status_code == 302 and response.url == f"{reverse('rcm:explorer')}?view=controls"
    assert not Control.objects.exists()


def test_discard_later_draft_returns_to_item(access, owner, reviewer):
    version = draft_by(owner, access)
    owner.post(url("submit", version))
    reviewer.post(url("approve", version))
    control = version.entity
    draft = v.propose_change(control, owner.user, "x", title="Other")
    response = owner.post(url("discard", draft), follow=True)
    assert response.redirect_chain[0][0] == control.get_absolute_url()
    assert "Draft discarded" in [str(m) for m in response.context["messages"]]
    assert control.versions.count() == 1
    assert ControlVersion.objects.filter(pk=draft.pk).count() == 0
