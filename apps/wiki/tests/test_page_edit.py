"""Checks the forms for creating and editing a guide."""

import pytest
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As
from apps.platforms.models import Platform
from apps.wiki.forms import PageForm
from apps.wiki.models import Page, Section
from apps.wiki.tests.support import make_page, page_post

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


def create(owner, **over):
    return owner.post(reverse("wiki:page_new"), page_post(**over))


def test_new_page_form_has_the_expected_fields(owner):
    html = owner.get(reverse("wiki:page_new")).content.decode()
    for text in ("Section", "Title", "Platform", "Page content", "Owner role", "Review by", "References"):
        assert text in html
    for gone in ("Page type", "Collection", "Summary", "Topic", "Stage", "Theme"):
        assert f">{gone}<" not in html
    for label in Section.labels:
        assert label in html
    assert "data-trac-editor" in html and "jodit.min.js" in html
    assert "Your change" not in html


def test_form_field_order():
    assert list(PageForm(with_summary=True).fields) == [
        "section", "title", "platform", "body", "owner_role", "review_by", "references", "change_summary",
    ]


@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_other_roles_cannot_open_or_post_the_forms(group):
    other = As(f"someone-{group}", group)
    assert other.get(reverse("wiki:page_new")).status_code == 403
    assert other.post(reverse("wiki:page_new"), page_post()).status_code == 403
    assert other.get(reverse("wiki:faq_new")).status_code == 403


def test_other_roles_cannot_edit_an_existing_page(owner, reviewer):
    page = make_page(owner.user, reviewer.user)
    assert As("reader", "ro").get(reverse("wiki:page_edit", args=[page.slug])).status_code == 403


def test_create_saves_a_draft_and_redirects_to_it(owner):
    response = create(owner, title="Backup guide")
    page = Page.objects.get()
    assert response.status_code == 302 and response.url == f"{page.get_absolute_url()}?version=1"
    version = page.versions.get()
    assert version.status == v.Status.DRAFT and version.proposed_by == owner.user
    assert (page.slug, version.title, version.section) == ("backup-guide", "Backup guide", "best_practice")
    assert version.platform is None and version.references == []


@pytest.mark.parametrize(
    "section,headings",
    [
        ("build", ["When to use this", "How to design it", "What good looks like"]),
        ("run", ["Before you start", "Steps", "Checks before you finish"]),
        ("best_practice", []),
        ("audit_prep", []),
    ],
)
def test_empty_body_gets_a_starter_outline_by_section(owner, section, headings):
    create(owner, section=section)
    body = Page.objects.get().versions.get().body
    assert body == "".join(f"<h2>{h}</h2>" for h in headings)


def test_written_body_is_kept_and_cleaned(owner):
    create(owner, body="<p>Mine</p><script>x()</script>")
    assert Page.objects.get().versions.get().body == "<p>Mine</p>"


def test_platform_can_be_set(owner):
    platform = Platform.objects.create(name="Splunk", categories=["logging"])
    create(owner, platform=platform.pk)
    assert Page.objects.get().versions.get().platform == platform


def test_same_title_gets_a_new_slug_and_reserved_words_are_skipped(owner):
    create(owner, title="Retention rules")
    create(owner, title="Retention rules")
    create(owner, title="FAQ")
    assert sorted(Page.objects.values_list("slug", flat=True)) == ["faq-2", "retention-rules", "retention-rules-2"]


def test_required_fields_are_checked(owner):
    response = create(owner, section="")
    assert response.status_code == 200 and not Page.objects.exists()
    assert "This isn&#x27;t saved yet." in response.content.decode() or "isn't saved yet" in response.content.decode()


def test_editing_your_draft_updates_it_in_place(owner):
    create(owner)
    page = Page.objects.get()
    url = reverse("wiki:page_edit", args=[page.slug])
    assert "Your change" not in owner.get(url).content.decode()
    owner.post(url, page_post(title="Renamed", section="run"))
    version = page.versions.get()
    assert (version.title, version.section, version.number) == ("Renamed", "run", 1)
    assert page.slug == "github-actions-runners"


def test_changing_a_published_page_proposes_version_two(owner, reviewer):
    page = make_page(owner.user, reviewer.user)
    url = reverse("wiki:page_edit", args=[page.slug])
    assert "Your change" in owner.get(url).content.decode()
    response = owner.post(url, page_post(body="<h2>New</h2>", change_summary="Rewrote it"))
    assert response.status_code == 302 and response.url.endswith("?version=2")
    draft = page.versions.get(number=2)
    assert draft.status == v.Status.DRAFT and draft.change_summary == "Rewrote it" and draft.body == "<h2>New</h2>"
    assert page.current().number == 1


def test_a_change_needs_a_summary(owner, reviewer):
    page = make_page(owner.user, reviewer.user)
    response = owner.post(reverse("wiki:page_edit", args=[page.slug]), page_post())
    assert response.status_code == 200 and page.versions.count() == 1


def test_someone_elses_open_change_blocks_editing(owner, reviewer):
    page = make_page(owner.user, reviewer.user)
    v.propose_change(page, owner.user, change_summary="First")
    html = reviewer.get(reverse("wiki:page_edit", args=[page.slug])).content.decode()
    assert "Someone else is already working on a change" in html
