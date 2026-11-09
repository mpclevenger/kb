"""Checks the FAQ page and creating or changing a question."""

import pytest
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As
from apps.wiki.models import Faq
from apps.wiki.tests.support import make_faq, make_page

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


@pytest.fixture
def reader():
    return As("reader", "ro")


def faq_post(**over):
    data = {"question": "Who approves exceptions?", "answer": "Tech Risk does.", "topic": "", "related_pages": []}
    data.update(over)
    return data


def test_faq_groups_by_topic_with_general_first(reader, owner, reviewer, access, other_topic):
    make_faq(owner.user, reviewer.user, question="Q about access", topic=access)
    make_faq(owner.user, reviewer.user, question="Q for everyone")
    make_faq(owner.user, reviewer.user, question="Q about the other topic", topic=other_topic)
    html = reader.get(reverse("wiki:faq")).content.decode()
    positions = [html.index(text) for text in ("General", "Q for everyone", access.name, "Q about access")]
    assert positions == sorted(positions)
    assert html.index("Q for everyone") < html.index("Q about access") < html.index("Q about the other topic")
    assert html.count("<details") == 3


def test_faq_shows_answer_and_published_related_pages_only(reader, owner, reviewer, access):
    published = make_page(owner.user, reviewer.user, title="Linked guide")
    draft = make_page(owner.user, reviewer.user, title="Hidden draft", publish_it=False)
    make_faq(owner.user, reviewer.user, related=[published, draft])
    html = reader.get(reverse("wiki:faq")).content.decode()
    assert "<p>Tech Risk does.</p>" in html and "<p>Ask early.</p>" in html
    assert f'href="{published.get_absolute_url()}"' in html
    assert "Hidden draft" not in html


def test_faq_hides_drafts_and_shows_edit_links_to_tech_risk_only(reader, owner, reviewer):
    faq = make_faq(owner.user, reviewer.user)
    make_faq(owner.user, reviewer.user, publish_it=False, question="Not yet")
    assert "Not yet" not in reader.get(reverse("wiki:faq")).content.decode()
    edit = reverse("wiki:faq_edit", args=[faq.pk])
    assert edit not in reader.get(reverse("wiki:faq")).content.decode()
    html = owner.get(reverse("wiki:faq")).content.decode()
    assert edit in html and reverse("wiki:faq_new") in html


def test_empty_faq_says_so(reader):
    assert "No questions yet" in reader.get(reverse("wiki:faq")).content.decode()


def test_create_question_flow(owner, reviewer, access):
    page = make_page(owner.user, reviewer.user)
    response = owner.post(reverse("wiki:faq_new"), faq_post(topic=access.pk, related_pages=[page.pk]))
    faq = Faq.objects.get()
    assert response.status_code == 302 and response.url == f"{faq.get_absolute_url()}?version=1"
    version = faq.versions.get()
    assert version.status == v.Status.DRAFT and version.topic == access
    assert list(version.related_pages.all()) == [page]
    # Draft view: hidden from readers, actions for Tech Risk.
    assert As("reader", "ro").get(faq.get_absolute_url()).status_code == 404
    html = owner.get(faq.get_absolute_url(), {"version": 1}).content.decode()
    assert "Draft, not official" in html and "Submit for review" in html and "Who approves exceptions?" in html
    # Submit, approve, then readers see it in the list.
    owner.post(reverse("workflow:submit", args=_workflow_args(version)))
    reviewer.post(reverse("workflow:approve", args=_workflow_args(version)))
    assert "Who approves exceptions?" in As("reader", "ro").get(reverse("wiki:faq")).content.decode()


def _workflow_args(version):
    from django.contrib.contenttypes.models import ContentType

    return [ContentType.objects.get_for_model(version).pk, version.pk]


def test_changing_a_published_question_proposes_a_new_version(owner, reviewer):
    faq = make_faq(owner.user, reviewer.user)
    url = reverse("wiki:faq_edit", args=[faq.pk])
    assert "Your change" in owner.get(url).content.decode()
    owner.post(url, faq_post(answer="Updated.", change_summary="Clearer"))
    draft = faq.versions.get(number=2)
    assert (draft.answer, draft.change_summary, draft.status) == ("Updated.", "Clearer", v.Status.DRAFT)
    assert faq.current().answer.startswith("Tech Risk does")


def test_related_pages_carry_over_to_the_new_version(owner, reviewer, access):
    page = make_page(owner.user, reviewer.user)
    faq = make_faq(owner.user, reviewer.user, related=[page])
    owner.get(reverse("wiki:faq_edit", args=[faq.pk]))
    owner.post(reverse("wiki:faq_edit", args=[faq.pk]), faq_post(related_pages=[page.pk], change_summary="x"))
    assert list(faq.versions.get(number=2).related_pages.all()) == [page]


def test_question_needs_text_and_only_tech_risk_may_post(owner, reader):
    assert owner.post(reverse("wiki:faq_new"), faq_post(question="")).status_code == 200
    assert not Faq.objects.exists()
    assert reader.post(reverse("wiki:faq_new"), faq_post()).status_code == 403


def test_related_pages_choices_are_published_pages_only(owner, reviewer, access):
    make_page(owner.user, reviewer.user, title="Visible page")
    make_page(owner.user, reviewer.user, title="Draft page", publish_it=False)
    html = owner.get(reverse("wiki:faq_new")).content.decode()
    assert "Visible page" in html and "Draft page" not in html


def test_discarding_a_first_question_draft_returns_to_the_faq(owner):
    owner.post(reverse("wiki:faq_new"), faq_post())
    version = Faq.objects.get().versions.get()
    response = owner.post(reverse("workflow:discard", args=_workflow_args(version)))
    assert response.url == reverse("wiki:faq")
