"""Checks the comment box, My comments and the Tech Risk Review queue."""

import pytest
from django.urls import reverse

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import EvidenceRule, EvidenceRuleVersion
from apps.core.tests.support import As
from apps.wiki.models import Faq, FaqVersion, Feedback, FeedbackStatus

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


@pytest.fixture
def tr():
    return As("tr", "tr")


@pytest.fixture
def tr2():
    return As("tr2", "tr")


@pytest.fixture
def reader():
    return As("reader", "co")


@pytest.fixture
def control(access, tr, tr2):
    entity, version = services.create_control(
        tr.user, access, title="Access review", why="Because.", owner_role="IAM",
        nature="detective", method="manual", frequency="monthly",
    )
    v.submit(version, tr.user)
    v.approve_and_publish(version, tr2.user)
    return entity


def comment_data(**extra):
    return {"path": "/rcm/controls/AC-01/", "label": "Access review", "section": "General", "comment": "Unclear.", **extra}


# Comment box

def test_comment_box_shows_on_control_page_with_general_fallback(reader, control):
    html = reader.get(control.get_absolute_url()).content.decode()
    assert "Comment on this page" in html
    assert "<option>General</option>" in html
    assert "Send comment" in html


@pytest.mark.parametrize("path", [
    "/manage/", "/review/my-comments/", "/ui/gallery/", "/rcm/new/control/",
    "/guides/new/page/", "/guides/new/faq/", "/platforms/category/database/guidance/",
])
def test_comment_box_hidden_on_forms_manage_review_and_gallery(tr, path):
    assert "Comment on this page" not in tr.get(path).content.decode()


def test_posting_a_comment_saves_it_and_redirects_with_message(reader, control):
    response = reader.post(reverse("review:comment"), comment_data(section="How to run it"), follow=True)
    item = Feedback.objects.get()
    assert (item.about_url, item.section, item.comment, item.submitted_by) == (
        "/rcm/controls/AC-01/", "How to run it", "Unclear.", reader.user
    )
    assert response.redirect_chain[-1][0] == "/rcm/controls/AC-01/"
    page = response.content.decode()
    assert "your comment was sent to Tech Risk" in page
    assert reverse("review:mine") in page


def test_off_site_path_is_rejected(reader):
    for path in ("https://evil.example/", "//evil.example/"):
        response = reader.post(reverse("review:comment"), comment_data(path=path))
        assert response.url == reverse("review:mine")
    assert not Feedback.objects.exists()


def test_empty_comment_is_rejected_and_returns_to_page(reader, control):
    response = reader.post(reverse("review:comment"), comment_data(comment=" "), follow=True)
    assert not Feedback.objects.exists()
    assert "Write a comment first." in response.content.decode()


# My comments

def test_my_comments_shows_only_own_with_reply(tr, reader):
    mine = Feedback.objects.create(
        about_url="/topics/x/", about_label="Topic X", section="General", comment="Mine", submitted_by=reader.user,
        response="Fixed next week", status=FeedbackStatus.PLANNED,
    )
    Feedback.objects.create(
        about_url="/topics/y/", about_label="Topic Y", section="General", comment="Theirs", submitted_by=tr.user
    )
    html = reader.get(reverse("review:mine")).content.decode()
    assert mine.comment in html and "Fixed next week" in html and "Planned" in html
    assert "Theirs" not in html


# Review queue

def test_queue_is_for_tech_risk_only(reader):
    assert reader.get(reverse("review:queue")).status_code == 403
    assert reader.post(reverse("review:respond", args=[1]), {"status": "done"}).status_code == 403


def test_queue_lists_in_review_versions_of_several_types(tr, tr2, access):
    _, control_version = services.create_control(
        tr2.user, access, title="Access review", why="Because.", owner_role="IAM",
        nature="detective", method="manual", frequency="monthly",
    )
    v.submit(control_version, tr2.user)
    _, faq_version = v.create_entity(Faq, FaqVersion, tr.user, question="Do we review?", answer="Yes.")
    v.submit(faq_version, tr.user)
    html = tr.get(reverse("review:queue")).content.decode()
    assert "AC-01 Access review v1" in html and "Control" in html
    assert 'href="/rcm/controls/AC-01/?version=1"' in html
    assert "Do we review? v1" in html and "FAQ 1" not in html and "Faq" in html
    assert html.count("Yours — another Tech Risk member must approve") == 1


def test_queue_filters_comments_by_status_with_counts(tr, reader):
    for status in (FeedbackStatus.NEW, FeedbackStatus.NEW, FeedbackStatus.DONE):
        Feedback.objects.create(
            about_url="/topics/x/", about_label="Topic X", section="General", comment=f"c-{status}",
            submitted_by=reader.user, status=status,
        )
    html = tr.get(reverse("review:queue")).content.decode()
    assert "New (2)" in html and "Done (1)" in html
    assert html.count("c-new") == 2 and "c-done" not in html
    assert "c-done" in tr.get(reverse("review:queue"), {"status": "done"}).content.decode()


def test_queue_has_all_tab_and_filters_by_it(tr, reader):
    for status in (FeedbackStatus.NEW, FeedbackStatus.DONE):
        Feedback.objects.create(
            about_url="/topics/x/", about_label="Topic X", section="General", comment=f"c-{status}",
            submitted_by=reader.user, status=status,
        )
    html = tr.get(reverse("review:queue")).content.decode()
    assert "All (2)" in html and 'href="?status=all"' in html
    assert "status-tab" in html and "nav-pills" not in html
    everything = tr.get(reverse("review:queue"), {"status": "all"}).content.decode()
    assert "c-new" in everything and "c-done" in everything
    assert 'class="status-tab active" href="?status=all"' in everything


def test_first_drafts_use_their_own_name(tr, tr2, access):
    _, risk_version = services.create_risk(tr2.user, access, title="Leavers keep access", statement="s", owner_role="IAM")
    v.submit(risk_version, tr2.user)
    _, rule_version = v.create_entity(EvidenceRule, EvidenceRuleVersion, tr.user, name="Screenshot standard", items=["x"])
    v.submit(rule_version, tr.user)
    html = tr.get(reverse("review:queue")).content.decode()
    assert "R-AC-01 Leavers keep access v1" in html
    assert "Screenshot standard v1" in html and "Evidence rule 1" not in html


def test_respond_updates_status_and_reply(tr, reader):
    item = Feedback.objects.create(
        about_url="/topics/x/", about_label="X", section="General", comment="hi", submitted_by=reader.user
    )
    tr.post(reverse("review:respond", args=[item.pk]), {"status": "planned", "response": "Next quarter"})
    item.refresh_from_db()
    assert (item.status, item.response, item.handled_by) == ("planned", "Next quarter", tr.user)


def test_declining_needs_a_reply(tr, reader):
    item = Feedback.objects.create(
        about_url="/topics/x/", about_label="X", section="General", comment="hi", submitted_by=reader.user
    )
    response = tr.post(reverse("review:respond", args=[item.pk]), {"status": "declined", "response": " "}, follow=True)
    item.refresh_from_db()
    assert item.status == FeedbackStatus.NEW
    assert "Say why when declining." in response.content.decode()


def test_unknown_status_is_a_bad_request(tr, reader):
    item = Feedback.objects.create(
        about_url="/topics/x/", about_label="X", section="General", comment="hi", submitted_by=reader.user
    )
    assert tr.post(reverse("review:respond", args=[item.pk]), {"status": "bogus"}).status_code == 400


# Confirm handler

def test_discard_button_carries_confirm_message_and_page_still_renders(tr, access):
    _, version = services.create_control(
        tr.user, access, title="Draft", why="Because.", owner_role="IAM",
        nature="detective", method="manual", frequency="monthly",
    )
    html = tr.get(version.entity.get_absolute_url()).content.decode()
    assert 'data-confirm="Discard this draft?' in html
