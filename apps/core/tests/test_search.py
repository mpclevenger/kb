"""Checks the site-wide search: what it finds, what it hides and how it handles odd queries."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.roles import TECH_RISK
from apps.core.search import SearchItem, query_words, run_search
from apps.core.tests.support import make_user, published_control
from apps.platforms.models import Platform
from apps.platforms.tests.support import publish_guidance
from apps.wiki.tests.support import count_queries, make_page

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


@pytest.fixture
def people():
    return make_user("proposer", TECH_RISK), make_user("approver", TECH_RISK)


def search(client, q):
    return client.get(reverse("core:search"), {"q": q}).content.decode()


def test_finds_a_guide_by_a_word_in_its_body(client, people):
    page = make_page(*people, title="Reporting basics", body="<p>Build a <b>dashboard</b> for owners.</p>")
    html = search(client, "dashboard")
    assert page.get_absolute_url() in html and "Reporting basics" in html
    assert "<mark>dashboard</mark>" in html
    assert "<b>" not in html.split("Reporting basics", 1)[1]


def test_finds_a_control_by_its_criteria(client, people, access):
    control, _ = published_control(
        access, *people, title="Quarterly review", criteria=[{"name": "Evidence", "items": ["Screenshot of the dashboard"]}]
    )
    html = search(client, "dashboard screenshot")
    assert control.get_absolute_url() in html and "Controls (1)" in html


def test_finds_a_platform_by_name_with_the_category_link(client):
    platform = Platform.objects.get(name="Databricks")
    html = search(client, "databricks")
    assert f'href="{platform.get_absolute_url()}"' in html
    assert "Library (" in html


def test_library_guidance_lines_are_searched(client):
    publish_guidance({"category": "database"}, intro="Keep a zebrafish register.")
    html = search(client, "zebrafish")
    assert reverse("platforms:category", args=["database"]) in html


def test_drafts_are_never_shown(client, people, access):
    make_page(*people, title="Secret draft guide", body="<p>quokka</p>", publish_it=False)
    from apps.rcm import services
    services.create_control(
        people[0], access, title="Draft quokka control", why="w", owner_role="o", nature="detective",
        method="manual", frequency="monthly",
    )
    html = search(client, "quokka")
    assert "Secret draft guide" not in html and "Draft quokka control" not in html
    assert "No results for" in html


def test_unknown_words_are_left_out(client, people):
    make_page(*people, title="Dashboard guide", body="<p>All about Databricks.</p>")
    html = search(client, "ASV dashboard Databricks")
    assert "No results for 'asv' on its own, so it was left out." in html
    assert "Dashboard guide" in html


def test_items_with_more_of_the_words_rank_first_and_related_items_still_show():
    items = [
        SearchItem("guide", "Report guide", "/report/", "building a dashboard a control relies on"),
        SearchItem("guide", "Platform guide", "/platform/", "databricks workspaces and a dashboard section"),
        SearchItem("guide", "Other guide", "/other/", "databricks clusters"),
    ]
    results, _ = run_search("dashboard databricks", items)
    urls = [r.item.url for r in results["guide"]]
    assert urls[0] == "/platform/" and set(urls[1:]) == {"/report/", "/other/"}


def test_the_snippet_centers_on_the_least_common_word():
    filler = "databricks " * 40
    items = [
        SearchItem("guide", "Platform guide", "/p/", filler + "the dashboard section"),
        SearchItem("guide", "Another", "/a/", "databricks again"),
    ]
    results, _ = run_search("databricks dashboard", items)
    assert "<mark>dashboard</mark>" in results["guide"][0].snippet


def test_each_group_shows_at_most_its_best_results():
    from apps.core.search import MAX_PER_GROUP
    items = [SearchItem("guide", f"Guide {n}", f"/g{n}/", "access") for n in range(MAX_PER_GROUP + 3)]
    results, _ = run_search("access", items)
    assert len(results["guide"]) == MAX_PER_GROUP


@pytest.mark.usefixtures("seeded")
def test_the_search_page_has_no_comment_box(client):
    assert "Comment on this page" not in search(client, "access")


def test_short_words_and_case_are_ignored():
    assert query_words("An ASV Dashboard, of DB") == ["asv", "dashboard"]


def test_title_matches_rank_first():
    items = [
        SearchItem("guide", "Zebra notes", "/a/", "about access reviews"),
        SearchItem("guide", "Access reviews", "/b/", "other text"),
        SearchItem("guide", "Access reviews in detail", "/c/", "other text"),
    ]
    results, _ = run_search("access", items)
    assert [r.item.url for r in results["guide"]] == ["/b/", "/c/", "/a/"]


def test_the_query_is_escaped(client):
    html = search(client, '<script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_snippets_escape_content(client, people):
    make_page(*people, title="Escapes", body="<p>use &lt;img src=x&gt; with dashboard care</p>")
    html = search(client, "dashboard")
    assert "<img src=x>" not in html


def test_empty_query_shows_a_hint(client):
    html = search(client, "")
    assert "Type a word or two" in html


def test_top_bar_has_a_search_form(client):
    html = client.get(reverse("core:home")).content.decode()
    assert 'role="search"' in html and 'action="/search/"' in html
    assert 'name="q"' in html and "Search TRAC" in html
    assert 'placeholder="Search guides, controls and the Library"' in html


def test_query_count_is_flat_as_content_grows(client, people, access):
    url = reverse("core:search") + "?q=dashboard"
    make_page(*people, title="Dashboard one", body="<p>dashboard</p>")
    small = count_queries(client, url)
    for n in range(5):
        make_page(*people, title=f"Dashboard more {n}", body="<p>dashboard</p>")
        published_control(access, *people, title=f"Dashboard control {n}")
    assert count_queries(client, url) == small
