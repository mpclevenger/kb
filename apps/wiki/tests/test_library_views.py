"""Checks the guides index and the guide pages."""

import pytest
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As, anonymous
from apps.platforms.models import Platform
from apps.wiki.models import Section
from apps.wiki.tests.support import assert_in_html, make_page

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

INDEX = "wiki:index"


@pytest.fixture
def reader():
    return As("reader", "ro")


@pytest.fixture
def runners(owner, reviewer):
    platform = Platform.objects.create(name="GitHub Enterprise Server", categories=["engineering_tools"])
    return make_page(owner.user, reviewer.user, platform=platform)


@pytest.fixture
def design(owner, reviewer):
    return make_page(owner.user, reviewer.user, title="Designing a review control", section="build")


def test_section_choices_and_order():
    assert Section.values == ["build", "run", "best_practice", "audit_prep"]
    assert Section.labels == ["Build your controls", "Run your controls", "Best practices", "Audit prep"]


# Index

def test_index_band_has_no_subtitle(reader):
    html = reader.get(reverse(INDEX)).content.decode()
    assert_in_html('<h1 class="band-title">Best practices and guides</h1>', html)
    assert "band-summary" not in html
    assert "Guides and standards" not in html


def test_index_lists_rows_with_section_platform_and_review_date(reader, runners):
    html = reader.get(reverse(INDEX)).content.decode()
    row = html[html.index('<li class="library-row">'):]
    assert f'href="{runners.get_absolute_url()}"' in row and "GitHub Actions runners" in row
    assert "type-pill-section-best_practice" in row and "GitHub Enterprise Server" in row
    assert "Review by Jan 1, 2099" in row


def test_index_hides_unpublished_pages(reader, owner, reviewer):
    make_page(owner.user, reviewer.user, publish_it=False, title="Secret draft")
    assert "Secret draft" not in reader.get(reverse(INDEX)).content.decode()


@pytest.mark.usefixtures("design")
def test_index_has_a_card_per_section_without_counts(reader, runners):
    html = reader.get(reverse(INDEX)).content.decode()
    for label in Section.labels:
        assert label in html
    assert html.count('class="library-section-title"') == 4
    assert "library-section-count" not in html


@pytest.mark.usefixtures("design")
def test_cards_filter_the_list_and_mark_the_active_one(reader, runners):
    html = reader.get(reverse(INDEX), {"section": "build"}).content.decode()
    assert "Designing a review control" in html and "GitHub Actions runners" not in html
    assert html.count("library-section-active") == 1 and 'aria-current="true"' in html
    html = reader.get(reverse(INDEX), {"section": "bogus"}).content.decode()
    assert "Designing a review control" in html and "GitHub Actions runners" in html


def test_card_links_are_shareable_urls(reader):
    html = reader.get(reverse(INDEX)).content.decode()
    assert f'href="{reverse(INDEX)}?section=run"' in html and f'hx-get="{reverse(INDEX)}?section=run"' in html


def test_there_is_no_topic_filter(reader, runners):
    html = reader.get(reverse(INDEX)).content.decode()
    assert 'name="topic"' not in html and "All topics" not in html


def test_htmx_request_returns_only_the_list(reader, runners):
    response = reader.get(reverse(INDEX), {"section": "best_practice"}, HTTP_HX_REQUEST="true")
    html = response.content.decode()
    assert '<div id="library">' in html and "<html" not in html
    assert "GitHub Actions runners" in html and "library-section-title" in html
    assert "HX-Request" in response["Vary"]


def test_index_links_to_the_faq_only_as_a_card(reader):
    html = reader.get(reverse(INDEX)).content.decode()
    assert reverse("wiki:faq") in html


def test_audit_prep_is_the_index_filtered_to_audit_prep(reader, owner, reviewer, runners):
    make_page(owner.user, reviewer.user, title="Before your review", section="audit_prep")
    response = reader.get(reverse("wiki:audit_prep"))
    assert response.status_code == 302 and response.url == f"{reverse(INDEX)}?section=audit_prep"
    html = reader.get(response.url).content.decode()
    assert "Before your review" in html and "GitHub Actions runners" not in html


def test_new_page_button_only_for_tech_risk(reader, owner):
    assert "New page" not in reader.get(reverse(INDEX)).content.decode()
    assert reverse("wiki:page_new") in owner.get(reverse(INDEX)).content.decode()


def test_index_needs_a_role():
    assert anonymous().get(reverse(INDEX)).status_code == 403


# Page view

def test_page_header_has_section_pill_and_title_only(reader, runners):
    html = reader.get(runners.get_absolute_url()).content.decode()
    assert "type-pill-section-best_practice" in html and "Best practices</span>" in html
    assert "band-summary" not in html
    assert 'href="' + reverse(INDEX) + '"' in html and "Best practices and guides" in html


def test_page_shows_toc_body_and_footer(reader, runners):
    html = reader.get(runners.get_absolute_url()).content.decode()
    assert '<h2 class="section-card-title" id="purpose">Purpose</h2>' in html
    assert 'On this page' in html and 'href="#purpose"' in html and 'href="#detail"' in html
    assert "Governance" in html and "Owner role" in html and "Tech Risk" in html
    assert "Review by" in html and "Overdue" not in html


def test_page_shows_only_the_platform_chip(reader, runners, owner, reviewer):
    html = reader.get(runners.get_absolute_url()).content.decode()
    platform = Platform.objects.get(name="GitHub Enterprise Server")
    assert f'href="{platform.get_absolute_url()}"' in html and "Platform:" in html
    for label in ("Topic:", "Stage:", "Theme:"):
        assert label not in html
    plain = make_page(owner.user, reviewer.user, title="No platform")
    assert "Platform:" not in reader.get(plain.get_absolute_url()).content.decode()


def test_page_body_is_sanitized(reader, owner, reviewer):
    page = make_page(owner.user, reviewer.user, body='<h2>Safe</h2><script>alert(1)</script><p onclick="x()">Text</p>')
    html = reader.get(page.get_absolute_url()).content.decode()
    assert "<script>alert" not in html and "onclick" not in html and "Text" in html


def test_page_footer_flags_overdue_review(reader, owner, reviewer):
    from datetime import date

    page = make_page(owner.user, reviewer.user, review_by=date(2020, 1, 1))
    assert "Overdue" in reader.get(page.get_absolute_url()).content.decode()


def test_page_lists_references(reader, owner, reviewer):
    page = make_page(
        owner.user, reviewer.user, references=[{"label": "NIST SP 800-53", "url": "https://example.org/nist"}]
    )
    html = reader.get(page.get_absolute_url()).content.decode()
    assert 'href="https://example.org/nist"' in html and "NIST SP 800-53" in html


def test_page_has_comment_box(reader, runners):
    assert "Comment on this page" in reader.get(runners.get_absolute_url()).content.decode()


def test_unknown_page_is_404(reader):
    assert reader.get(reverse("wiki:page", args=["missing"])).status_code == 404


# Drafts and notices

def test_draft_hidden_from_readers_and_shown_to_tech_risk(reader, owner, reviewer):
    page = make_page(owner.user, reviewer.user, publish_it=False)
    assert reader.get(page.get_absolute_url()).status_code == 404
    html = owner.get(page.get_absolute_url()).content.decode()
    assert "Draft, not official" in html and "Submit for review" in html and "Edit draft" in html
    assert reviewer.get(page.get_absolute_url()).status_code == 200


def test_published_page_offers_propose_a_change_to_tech_risk_only(reader, owner, runners):
    assert "Propose a change" not in reader.get(runners.get_absolute_url()).content.decode()
    html = owner.get(runners.get_absolute_url()).content.decode()
    assert reverse("wiki:page_edit", args=[runners.slug]) in html and "Propose a change" in html


def test_open_proposal_notice_hides_the_draft_from_readers(reader, owner, runners):
    v.propose_change(runners, owner.user, change_summary="Tighten")
    html = reader.get(runners.get_absolute_url()).content.decode()
    assert "Someone is preparing an edit to this page." in html and "View the proposed version" not in html
    assert reader.get(runners.get_absolute_url(), {"version": 2}).status_code == 404
    assert "View the proposed version" in owner.get(runners.get_absolute_url()).content.decode()


def test_page_in_review_is_hidden_from_readers_and_awaits_another_approver(reader, owner, reviewer):
    page = make_page(owner.user, reviewer.user, publish_it=False)
    v.submit(page.versions.get(), owner.user)
    assert reader.get(page.get_absolute_url()).status_code == 404
    assert "Waiting for your decision" in reviewer.get(page.get_absolute_url()).content.decode()


def test_short_guides_show_sections_as_open_cards(reader, runners):
    html = reader.get(runners.get_absolute_url()).content.decode()
    assert html.count('<details class="section-card section-card-neutral" open>') == 1


def test_long_guides_start_with_every_section_collapsed(owner, reviewer, reader):
    body = "<p>Intro text.</p>" + "".join(f"<h2>Stage {n}</h2><p>Detail {n}.</p>" for n in range(6))
    page = make_page(owner.user, reviewer.user, title="Long guide", body=body)
    html = reader.get(page.get_absolute_url()).content.decode()
    assert html.count('<details class="section-card section-card-neutral">') == 6
    assert "section-card-neutral\" open" not in html
    assert 'class="trac-paper library-body library-intro"><p>Intro text.</p>' in html
    assert 'id="stage-3"' in html and "data-section-toolbar" in html
