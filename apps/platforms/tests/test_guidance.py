"""Checks the guidance Tech Risk writes for categories and platforms."""

import json

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As, make_user
from apps.platforms.models import Guidance, GuidanceVersion, Platform

from .support import publish_guidance, question, tech_risk_pair

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


@pytest.fixture
def author(sso):
    return As("author", "tr")


@pytest.fixture
def approver(sso):
    return As("approver", "tr")


def edit_url(**kwargs):
    return reverse("platforms:guidance_edit", kwargs=kwargs)


def form_data(**over):
    data = {"intro": "How we look after databases.", f"line_{question('Access').pk}": "Limit admin access.",
            "references": json.dumps([{"label": "CIS", "url": "https://example.com"}])}
    data.update(over)
    return data


# Model

def test_guidance_needs_exactly_one_target():
    user = make_user("u", "tech_risk")
    sql = Platform.objects.get(name="SQL Server")
    for fields in ({}, {"category": "database", "platform": sql}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Guidance.objects.create(created_by=user, **fields)


def test_guidance_is_unique_per_category_and_per_platform():
    user = make_user("u", "tech_risk")
    sql = Platform.objects.get(name="SQL Server")
    Guidance.objects.create(created_by=user, category="database")
    Guidance.objects.create(created_by=user, platform=sql)
    Guidance.objects.create(created_by=user, category="identity")
    for fields in ({"category": "database"}, {"platform": sql}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Guidance.objects.create(created_by=user, **fields)


def version(**content):
    return GuidanceVersion(**content)


def test_lines_are_validated():
    access = question("Access").pk
    version(lines=[{"question": access, "text": "Limit admin access."}]).full_clean(exclude=["entity", "number", "proposed_by"])
    for bad in (
        [{"question": access, "text": "  "}],
        [{"question": 999999, "text": "x"}],
        [{"question": access, "text": "x"}, {"question": access, "text": "y"}],
        [{"question": "1", "text": "x"}],
        [{"text": "x"}],
        {"question": access},
    ):
        with pytest.raises(ValidationError):
            version(lines=bad).full_clean(exclude=["entity", "number", "proposed_by"])


def test_references_are_validated():
    with pytest.raises(ValidationError):
        version(references=[{"label": "x", "url": "ftp://nope"}]).full_clean(exclude=["entity", "number", "proposed_by"])


# Edit form

@pytest.mark.usefixtures("sso")
def test_edit_form_is_403_for_everyone_but_tech_risk():
    for group in ("co", "ro", "aud"):
        who = As(f"user-{group}", group)
        assert who.get(edit_url(key="database")).status_code == 403
        assert who.post(edit_url(slug="sql-server"), form_data()).status_code == 403


def test_edit_form_unknown_targets_are_404(author):
    assert author.get(edit_url(key="mainframe")).status_code == 404
    assert author.get(edit_url(slug="nope")).status_code == 404


def test_edit_form_has_a_field_per_question_and_a_references_editor(author):
    html = author.get(edit_url(key="database")).content.decode()
    for q in __import__("apps.platforms.selectors", fromlist=["x"]).active_questions():
        assert f'name="line_{q.pk}"' in html and q.text in html
    assert 'name="intro"' in html and "data-rows-editor" in html
    assert "What are you changing" not in html


def test_create_submit_approve_publishes_lines_on_the_pages(author, approver):
    page = reverse("platforms:category", args=["database"])
    assert "Limit admin access." not in author.get(page).content.decode()

    response = author.post(edit_url(key="database"), form_data())
    assert response.status_code == 302
    guidance = Guidance.objects.get(category="database")
    draft = guidance.open_proposal()
    assert draft.status == v.Status.DRAFT and draft.lines == [{"question": question("Access").pk, "text": "Limit admin access."}]
    assert "Limit admin access." not in author.get(page).content.decode()

    editing = author.get(edit_url(key="database")).content.decode()
    assert "Submit for review" in editing and "Limit admin access." in editing

    author.post(reverse("workflow:submit", args=[_ctype(), draft.pk]))
    draft.refresh_from_db()
    assert draft.status == v.Status.IN_REVIEW
    assert "Your change is in review" in author.get(edit_url(key="database")).content.decode()
    waiting = approver.get(edit_url(key="database")).content.decode()
    assert "Approve and publish" in waiting and "Limit admin access." in waiting

    approver.post(reverse("workflow:approve", args=[_ctype(), draft.pk]))
    html = author.get(page).content.decode()
    assert "How we look after databases." in html and "Limit admin access." in html and "CIS" in html


def _ctype():
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(GuidanceVersion).pk


def test_editing_published_guidance_proposes_a_change_with_a_summary(author):
    guidance = publish_guidance({"category": "database"}, intro="Old.", lines={"Access": "Old line."})
    html = author.get(edit_url(key="database")).content.decode()
    assert "Old line." in html and "What are you changing" in html
    response = author.post(edit_url(key="database"), form_data(change_summary="Reworded."))
    assert response.status_code == 302
    draft = guidance.open_proposal()
    assert draft.number == 2 and draft.change_summary == "Reworded." and draft.lines[0]["text"] == "Limit admin access."
    assert guidance.current().intro == "Old."


def test_change_summary_is_required_for_a_new_version(author):
    publish_guidance({"category": "database"})
    html = author.post(edit_url(key="database"), form_data()).content.decode()
    assert "This isn't saved yet." in html


def test_saving_again_updates_the_same_draft_and_blank_lines_are_dropped(author):
    author.post(edit_url(slug="sql-server"), form_data())
    author.post(edit_url(slug="sql-server"), form_data(**{f"line_{question('Access').pk}": "", f"line_{question('Change').pk}": "Review changes."}))
    guidance = Guidance.objects.get(platform__slug="sql-server")
    assert guidance.versions.count() == 1
    assert guidance.open_proposal().lines == [{"question": question("Change").pk, "text": "Review changes."}]


def test_invalid_references_show_an_error(author):
    html = author.post(edit_url(key="database"), form_data(references=json.dumps([{"label": "x", "url": "ftp://bad"}]))).content.decode()
    assert "must start with https://" in html
    assert not Guidance.objects.exists()


def test_someone_elses_draft_blocks_editing(author):
    guidance = publish_guidance({"category": "database"})
    other_proposer, _ = tech_risk_pair("other")
    v.propose_change(guidance, other_proposer, "Another change", intro="Elsewhere")
    html = author.get(edit_url(key="database")).content.decode()
    assert "Someone else is already working" in html and "<form method=\"post\" novalidate>" not in html
    assert "Elsewhere" in html


def test_guidance_lines_render_as_bullets_and_the_form_takes_them(author):
    bullets = "Before the list.\n- Named admins\n- <i>Reviewed</i>"
    response = author.post(edit_url(key="database"), form_data(**{f"line_{question('Access').pk}": bullets}))
    assert response.status_code == 302
    version = GuidanceVersion.objects.get(entity__category="database")
    assert version.lines[0]["text"] == bullets
    form = author.get(edit_url(key="database")).content.decode()
    assert "- Named admins" in form and "Start a line with" in form
    v.submit(version, author.user)
    v.approve_and_publish(version, make_user("second", "tech_risk"))
    html = author.get(reverse("platforms:category", args=["database"])).content.decode()
    assert "<p>Before the list.</p><ul><li>Named admins</li><li>&lt;i&gt;Reviewed&lt;/i&gt;</li></ul>" in html
