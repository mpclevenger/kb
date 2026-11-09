"""Checks FAQ approval and the visitor comment rules."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.accounts.roles import READ_ONLY, TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import make_user
from apps.wiki import feedback as fb
from apps.wiki.models import Faq, FaqVersion, FeedbackStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def reader():
    return make_user("reader", READ_ONLY)


@pytest.fixture
def risk():
    return make_user("risk", TECH_RISK)


def test_faq_goes_through_approval(risk):
    second = make_user("risk2", TECH_RISK)
    faq, version = v.create_entity(Faq, FaqVersion, second, question="Do service accounts need review?", answer="Yes.")
    assert faq.current() is None
    v.submit(version, second)
    v.approve_and_publish(version, risk)
    assert str(faq) == "Do service accounts need review?"


def test_related_pages_locked_after_submit(risk):
    from apps.wiki.models import Page

    page = Page.objects.create(slug="x", created_by=risk)
    _, version = v.create_entity(Faq, FaqVersion, risk, question="q", answer="a")
    v.submit(version, risk)
    with pytest.raises(v.ImmutableVersionError):
        version.related_pages.add(page)


def test_anyone_can_comment(reader):
    item = fb.leave_feedback(reader, "/rcm/controls/AC-01/", "AC-01 Quarterly user access review",
                             "How to run it", "Step 3 is unclear")
    assert (item.submitted_by, item.status) == (reader, FeedbackStatus.NEW)


def test_comment_must_have_text_and_stay_on_site(reader):
    with pytest.raises(ValidationError):
        fb.leave_feedback(reader, "/topics/x/", "x", "General", "  ")
    for url in ("https://evil.example/", "//evil.example/"):
        with pytest.raises(ValidationError):
            fb.leave_feedback(reader, url, "x", "General", "hi")


def test_only_tech_risk_responds_and_decline_needs_reason(reader, risk):
    item = fb.leave_feedback(reader, "/topics/x/", "x", "General", "hi")
    with pytest.raises(PermissionDenied):
        fb.respond(item, reader, FeedbackStatus.DONE)
    with pytest.raises(ValidationError):
        fb.respond(item, risk, FeedbackStatus.DECLINED)
    fb.respond(item, risk, FeedbackStatus.PLANNED, "Adding next quarter")
    item.refresh_from_db()
    assert item.status == FeedbackStatus.PLANNED and item.handled_by == risk
