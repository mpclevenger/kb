"""Checks the Library and category pages, including switching on a platform's specifics."""

from datetime import date

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.accounts.roles import TECH_RISK
from apps.core.tests.support import As, make_user
from apps.platforms.categories import Category
from apps.platforms.models import AspectQuestion, Platform

from apps.wiki.tests.support import assert_in_html, count_queries

from .support import publish_control, publish_guidance

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


@pytest.fixture
def client():
    c = Client()
    c.force_login(make_user("reader", TECH_RISK))
    return c


def get(client, url):
    return client.get(url).content.decode()


def category_page(client, key):
    return get(client, reverse("platforms:category", args=[key]))


def platform_page(client, name):
    return get(client, Platform.objects.get(name=name).get_absolute_url())


def section(html, start, end):
    html = html[html.index(start):]
    return html[: html.index(end)]


# Library (Home)

def test_library_is_the_home_page_with_search_tabs_and_nine_cards(client):
    html = get(client, reverse("core:library"))
    assert reverse("core:library") == "/library/"
    assert "<h1" in html and ">Library<" in html
    assert html.index("data-filter-input") < html.index('class="library-tabs"') < html.index('class="category-cards"')
    assert "js/filter.js" in html
    tabs = section(html, 'class="library-tabs"', "</nav>")
    assert f'<a href="{reverse("core:library")}" aria-current="page">By technology</a>' in tabs
    assert f'<a href="{reverse("topics:index")}">By risk topic</a>' in tabs
    assert html.count('class="category-card ') == 9


def test_old_library_url_redirects_to_home(client):
    response = client.get("/platforms/")
    assert response.status_code == 302 and response["Location"] == reverse("core:library")


def test_guidance_script_loads_only_on_the_library(client):
    assert "js/filter.js" not in category_page(client, "database")


def test_library_has_two_groups_and_categories_in_order(client):
    html = get(client, reverse("core:library"))
    stack, shared = html.index('id="the-stack"'), html.index('id="shared-services"')
    assert ">The stack</h2>" in html and ">Shared services</h2>" in html and stack < shared
    positions = [html.index(f'category-card category-{key}"') for key in Category.values]
    assert positions == sorted(positions)
    assert stack < html.index('category-card category-network"') < shared < html.index('category-card category-identity"')


def card(html, key):
    html = html[html.index(f'class="category-card category-{key}"'):]
    return html[: html.index("</ul>")]


def test_card_has_a_top_bar_class_a_linked_title_and_platform_chips(client):
    html = get(client, reverse("core:library"))
    database = card(html, "database")
    assert f'<a class="category-card-name" href="{reverse("platforms:category", args=["database"])}">Database</a>' in database
    sql = Platform.objects.get(name="SQL Server")
    assert f'<a class="platform-chip" href="{sql.get_absolute_url()}">SQL Server</a>' in database
    assert "stretched-link" not in database
    assert "border-top: 5px solid var(--category)" in open("static/css/guidance.css").read()


def test_platform_appears_on_every_card_it_belongs_to(client):
    html = get(client, reverse("core:library"))
    aws = Platform.objects.get(name="AWS")
    for key in aws.categories:
        assert f'href="{aws.url_in(key)}">AWS</a>' in card(html, key), key  # opens that card's page with AWS on
    assert html.count(">AWS</a>") == 4
    assert "AWS" not in card(html, "jobs") and "AWS" not in card(html, "network")


def test_cards_list_no_services(client):
    html = get(client, reverse("core:library"))
    for name in ("RDS", "IAM", "Appliance", "Unity Catalog"):
        assert name not in html


def test_library_skips_inactive_platforms(client):
    Platform.objects.filter(name="VPN").update(is_active=False)
    assert "VPN" not in get(client, reverse("core:library"))


def test_library_tabs_mark_the_topic_tab_when_asked():
    from django.template.loader import render_to_string

    tabs = render_to_string("components/library_tabs.html", {"active": "topic"})
    assert f'<a href="{reverse("topics:index")}" aria-current="page">By risk topic</a>' in tabs
    assert "By technology</a>" in tabs and tabs.count("aria-current") == 1


# Category page

def test_category_page_band_heading_and_platform_pills(client):
    html = category_page(client, "jobs")
    assert 'class="guidance-band category-jobs"' in html
    assert '<h1 class="band-title">Jobs and interfaces</h1>' in html
    assert ">Well-controlled jobs and interfaces</h2>" in html
    crumbs = section(html, 'aria-label="Breadcrumb"', "</nav>")
    assert crumbs.index("Library") < crumbs.index("The stack") and ">Home<" not in crumbs
    pills = section(html, 'aria-label="Show specifics for"', "</ul>")
    for name in ("In-house job scheduler", "SQL Server", "Windows Server", "Splunk", "Databricks", "GitHub Enterprise Server"):
        assert f">{name}</a>" in pills
    assert 'href="/platforms/category/jobs/?platform=sql-server" role="button" aria-pressed="false" data-platform-toggle="sql-server"' in pills
    assert "AWS" not in pills and "VPN" not in pills
    assert "Shared services" in section(category_page(client, "identity"), 'aria-label="Breadcrumb"', "</nav>")


def test_selected_pill_is_pressed_and_its_link_switches_it_off(client):
    html = get(client, reverse("platforms:category", args=["jobs"]) + "?platform=sql-server")
    pills = section(html, 'aria-label="Show specifics for"', "</ul>")
    assert 'href="/platforms/category/jobs/" role="button" aria-pressed="true" data-platform-toggle="sql-server"' in pills
    assert 'href="/platforms/category/jobs/?platform=sql-server&amp;platform=splunk"' in pills


def test_platforms_not_on_the_page_are_ignored_in_the_address(client):
    html = get(client, reverse("platforms:category", args=["jobs"]) + "?platform=vpn&platform=nope")
    assert 'aria-pressed="true"' not in html


def test_every_category_page_has_its_heading(client):
    for category in Category:
        assert f">{category.heading}</h2>" in category_page(client, category.value)


def test_category_page_shows_every_aspect_row_with_gap_badges(client):
    html = category_page(client, "network")
    assert html.count('class="place-row"') == AspectQuestion.objects.count()
    assert html.count("No control yet") == AspectQuestion.objects.count()
    assert html.count("Guidance coming soon") == AspectQuestion.objects.count()


def test_category_rows_show_published_guidance_and_link_to_the_topic(client):
    publish_guidance({"category": "database"}, intro="How we look after databases.",
                     lines={"Access": "Limit admin access."}, references=[{"label": "CIS", "url": "https://example.com"}])
    html = category_page(client, "database")
    assert "How we look after databases." in html and "Limit admin access." in html
    assert 'href="https://example.com"' in html and ">CIS<" in html
    access = AspectQuestion.objects.get(label="Access")
    assert f'<a class="place-label" href="{reverse("topics:detail", args=[access.topic.slug])}">Access</a>' in html
    assert html.count("Guidance coming soon") == AspectQuestion.objects.count() - 1


def test_category_page_without_guidance_has_no_intro_and_no_references(client):
    html = category_page(client, "database")
    assert "band-summary" not in html and 'id="references-heading"' not in html


def test_category_rows_match_controls_by_category_or_platform_tag_and_topic(client):
    by_category = publish_control("MA", title="Category tagged", categories=[Category.JOBS])
    by_platform = publish_control("MA", [Platform.objects.get(name="Splunk")], title="Platform tagged")
    other_category = publish_control("MA", title="Other category", categories=[Category.DATABASE])
    other_topic = publish_control("MC", title="Other topic", categories=[Category.JOBS])
    html = category_page(client, "jobs")
    access = section(html, ">Access</a>", "</li>")
    assert by_category.ident in access and by_platform.ident in access
    assert other_category.ident not in html
    assert other_topic.ident not in access and other_topic.ident in html
    assert section(html, ">Recovery</a>", "</li>").count("No control yet") == 1


@pytest.mark.usefixtures("sso")
def test_edit_button_only_for_tech_risk():
    url = reverse("platforms:category", args=["database"])
    edit = reverse("platforms:guidance_edit", kwargs={"key": "database"})
    assert f'href="{edit}"' in As("author", "tr").get(url).content.decode()
    assert edit not in As("reader", "ro").get(url).content.decode()


def test_category_unknown_is_404(client):
    assert client.get("/platforms/category/mainframe/").status_code == 404


# Platform specifics on a category page (platforms no longer have their own page)

def database_page(client, *slugs):
    query = "&".join(f"platform={s}" for s in slugs)
    return get(client, reverse("platforms:category", args=["database"]) + (f"?{query}" if query else ""))


def test_platform_lines_sit_under_the_matching_row_and_show_only_when_switched_on(client):
    sql = Platform.objects.get(name="SQL Server")
    publish_guidance({"category": "database"}, lines={"Access": "Limit admin access."})
    publish_guidance({"platform": sql}, tag="p", lines={"Access": "Treat sysadmin and db_owner as privileged roles."})
    off = section(database_page(client), ">Access</a>", "</li>")
    assert "Limit admin access." in off
    assert '<div class="platform-specific" data-platform-content="sql-server" hidden>' in off
    assert "On SQL Server" in off and "Treat sysadmin and db_owner as privileged roles." in off
    on = section(database_page(client, "sql-server"), ">Access</a>", "</li>")
    assert '<div class="platform-specific" data-platform-content="sql-server">' in on
    assert on.index("Limit admin access.") < on.index("Treat sysadmin")
    assert "On SQL Server" not in section(database_page(client), ">Change</a>", "</li>")


def test_several_platforms_can_be_switched_on_together(client):
    sql, windows = Platform.objects.get(name="SQL Server"), Platform.objects.get(name="Windows Server")
    Platform.objects.filter(pk=windows.pk).update(categories=["operating_system", "database"])
    publish_guidance({"platform": sql}, tag="p", lines={"Access": "SQL line."})
    publish_guidance({"platform": windows}, tag="w", lines={"Access": "Windows line."})
    access = section(database_page(client, "sql-server", "windows-server"), ">Access</a>", "</li>")
    assert access.count('class="platform-specific"') == 2 and " hidden>" not in access


def test_platform_panel_shows_intro_facts_documentation_runs_on_guides_and_references(client):
    from apps.core import versioning as v
    from apps.wiki.models import Page, PageVersion
    from .support import tech_risk_pair

    sql = Platform.objects.get(name="SQL Server")
    Platform.objects.filter(pk=sql.pk).update(owner="Database team")
    publish_guidance({"platform": sql}, tag="p", intro="SQL Server instances on Windows.",
                     references=[{"label": "SQL hardening", "url": "https://example.com/sql"}])
    owner, approver = tech_risk_pair("guide")
    page, version = v.create_entity(
        Page, PageVersion, owner, {"slug": "sql-admin"}, title="SQL Server admin guide", section="best_practice",
        platform=sql, owner_role="o", review_by=date(2027, 1, 1),
    )
    v.submit(version, owner)
    v.approve_and_publish(version, approver)
    panel = section(database_page(client, "sql-server"), 'aria-label="About SQL Server"', "</section>")
    assert "hidden" not in panel[:80]
    assert "SQL Server instances on Windows." in panel and "Database team" in panel and "On-premises" in panel
    assert 'href="/platforms/category/jobs/?platform=sql-server">Jobs and interfaces</a>' in panel
    assert 'aria-current="page">Database</a>' in panel
    windows = Platform.objects.get(name="Windows Server")
    assert f'Runs on: <a class="platform-chip" href="{windows.get_absolute_url()}">Windows Server</a>' in panel
    assert 'href="https://learn.microsoft.com/sql/sql-server/" target="_blank" rel="noopener noreferrer">SQL Server documentation</a>' in panel
    assert 'type-pill-section-best_practice">Best practices<' in panel and '<a href="/guides/sql-admin/">SQL Server admin guide</a>' in panel
    assert 'href="https://example.com/sql"' in panel


def test_panel_is_hidden_until_switched_on_and_notes_when_nothing_is_specific(client):
    html = database_page(client)
    assert '<section class="platform-notes" data-platform-content="sql-server" aria-label="About SQL Server" hidden>' in html
    assert "No SQL Server-specific items on this page yet" in section(html, 'aria-label="About SQL Server"', "</section>")


def test_runs_on_is_hidden_when_the_platform_is_inactive(client):
    Platform.objects.filter(name="Windows Server").update(is_active=False)
    assert "Runs on:" not in section(database_page(client, "sql-server"), 'aria-label="About SQL Server"', "</section>")


@pytest.mark.usefixtures("sso")
def test_platform_edit_button_is_for_tech_risk_only():
    url = reverse("platforms:category", args=["database"]) + "?platform=sql-server"
    edit = reverse("platforms:guidance_edit", kwargs={"slug": "sql-server"})
    assert f'href="{edit}">Edit SQL Server guidance</a>' in As("author", "tr").get(url).content.decode()
    assert edit not in As("reader", "ro").get(url).content.decode()


def test_old_platform_address_opens_its_main_category_with_it_switched_on(client):
    response = client.get(reverse("platforms:detail", args=["sql-server"]))
    assert response.status_code == 302 and response["Location"] == "/platforms/category/database/?platform=sql-server"
    assert client.get(reverse("platforms:detail", args=["nope"])).status_code == 404
    Platform.objects.filter(name="VPN").update(is_active=False)
    assert client.get(reverse("platforms:detail", args=["vpn"])).status_code == 404


def test_library_pages_highlight_the_library_nav_which_points_home(client):
    for url in (reverse("core:library"), reverse("platforms:category", args=["jobs"]),
                Platform.objects.get(name="Splunk").get_absolute_url()):
        nav = section(get(client, url), 'aria-label="Primary"', "</nav>")
        assert_in_html('<a href="/library/" aria-current="page">Library</a>', nav)


def test_category_page_query_count_is_flat(client):
    sql = Platform.objects.get(name="SQL Server")
    url = reverse("platforms:category", args=["database"]) + "?platform=sql-server"
    publish_control("MA", platforms=[sql], title="First")
    small = count_queries(client, url)
    for n, prefix in enumerate(["MA", "MC", "LA", "VM"]):
        publish_control(prefix, platforms=[sql], title=f"More {n}")
    assert count_queries(client, url) == small
