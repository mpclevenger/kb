"""Checks the Library, category and platform pages."""

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
    html = get(client, reverse("core:home"))
    assert reverse("core:home") == "/"
    assert "<h1" in html and ">Library<" in html
    assert html.index("data-filter-input") < html.index('class="library-tabs"') < html.index('class="category-cards"')
    assert "js/filter.js" in html
    tabs = section(html, 'class="library-tabs"', "</nav>")
    assert f'<a href="{reverse("core:home")}" aria-current="page">By technology</a>' in tabs
    assert f'<a href="{reverse("topics:index")}">By risk topic</a>' in tabs
    assert html.count('class="category-card ') == 9


def test_old_library_url_redirects_to_home(client):
    response = client.get("/platforms/")
    assert response.status_code == 302 and response["Location"] == reverse("core:home")


def test_guidance_script_loads_only_on_the_library(client):
    assert "js/filter.js" not in category_page(client, "database")


def test_library_has_two_groups_and_categories_in_order(client):
    html = get(client, reverse("core:home"))
    stack, shared = html.index('id="the-stack"'), html.index('id="shared-services"')
    assert ">The stack</h2>" in html and ">Shared services</h2>" in html and stack < shared
    positions = [html.index(f'category-card category-{key}"') for key in Category.values]
    assert positions == sorted(positions)
    assert stack < html.index('category-card category-network"') < shared < html.index('category-card category-identity"')


def card(html, key):
    html = html[html.index(f'class="category-card category-{key}"'):]
    return html[: html.index("</ul>")]


def test_card_has_a_top_bar_class_a_linked_title_and_platform_chips(client):
    html = get(client, reverse("core:home"))
    database = card(html, "database")
    assert f'<a class="category-card-name" href="{reverse("platforms:category", args=["database"])}">Database</a>' in database
    sql = Platform.objects.get(name="SQL Server")
    assert f'<a class="platform-chip" href="{sql.get_absolute_url()}">SQL Server</a>' in database
    assert "stretched-link" not in database
    assert "border-top: 5px solid var(--category)" in open("static/css/guidance.css").read()


def test_platform_appears_on_every_card_it_belongs_to(client):
    html = get(client, reverse("core:home"))
    aws = Platform.objects.get(name="AWS").get_absolute_url()
    for key in Platform.objects.get(name="AWS").categories:
        assert f'href="{aws}">AWS</a>' in card(html, key), key
    assert html.count(f'href="{aws}">AWS</a>') == 4
    assert "AWS" not in card(html, "jobs") and "AWS" not in card(html, "network")


def test_cards_list_no_services(client):
    html = get(client, reverse("core:home"))
    for name in ("RDS", "IAM", "Appliance", "Unity Catalog"):
        assert name not in html


def test_library_skips_inactive_platforms(client):
    Platform.objects.filter(name="VPN").update(is_active=False)
    assert "VPN" not in get(client, reverse("core:home"))


def test_library_tabs_mark_the_topic_tab_when_asked():
    from django.template.loader import render_to_string

    tabs = render_to_string("components/library_tabs.html", {"active": "topic"})
    assert f'<a href="{reverse("topics:index")}" aria-current="page">By risk topic</a>' in tabs
    assert "By technology</a>" in tabs and tabs.count("aria-current") == 1


# Category page

def test_category_page_band_heading_and_applies_to_chips(client):
    html = category_page(client, "jobs")
    assert 'class="guidance-band category-jobs"' in html
    assert '<h1 class="band-title">Jobs and interfaces</h1>' in html
    assert ">Well-controlled jobs and interfaces</h2>" in html
    crumbs = section(html, 'aria-label="Breadcrumb"', "</nav>")
    assert crumbs.index("Library") < crumbs.index("The stack") and ">Home<" not in crumbs
    chips = section(html, 'aria-label="Applies to"', "</ul>")
    for name in ("In-house job scheduler", "SQL Server", "Windows Server", "Splunk", "Databricks", "GitHub Enterprise Server"):
        assert f">{name}</a>" in chips
    assert Platform.objects.get(name="SQL Server").get_absolute_url() in chips
    assert "AWS" not in chips and "VPN" not in chips
    assert "Shared services" in section(category_page(client, "identity"), 'aria-label="Breadcrumb"', "</nav>")


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
    by_category = publish_control("AC", title="Category tagged", categories=[Category.JOBS])
    by_platform = publish_control("AC", [Platform.objects.get(name="Splunk")], title="Platform tagged")
    other_category = publish_control("AC", title="Other category", categories=[Category.DATABASE])
    other_topic = publish_control("CM", title="Other topic", categories=[Category.JOBS])
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


# Platform page

def sql_page(client):
    return platform_page(client, "SQL Server")


def test_platform_page_band_has_primary_color_pills_for_every_category_facts_and_documentation(client):
    Platform.objects.filter(name="SQL Server").update(owner="Database team")
    html = sql_page(client)
    band = section(html, 'class="guidance-band category-database"', "</main>")
    assert '<h1 class="band-title">SQL Server</h1>' in band
    facts = section(band, 'class="guidance-facts"', "</div>")
    assert facts.index("category-database") < facts.index("category-jobs")
    assert "On-premises" in facts and "Database team" in facts
    docs = section(band, 'class="guidance-docs"', "</p>")
    assert 'Documentation:' in docs
    assert 'href="https://learn.microsoft.com/sql/sql-server/" target="_blank" rel="noopener noreferrer">SQL Server documentation</a>' in docs
    crumbs = section(html, 'aria-label="Breadcrumb"', "</nav>")
    assert crumbs.index("Library") < crumbs.index("The stack") < crumbs.index("Database") < crumbs.index("SQL Server")


def test_platform_band_color_follows_the_first_category(client):
    Platform.objects.filter(name="SQL Server").update(categories=["jobs", "database"])
    assert 'class="guidance-band category-jobs"' in sql_page(client)


def test_documentation_line_is_hidden_without_links(client):
    html = platform_page(client, "VPN")
    assert "Documentation:" not in html
    Platform.objects.filter(name="VPN").update(doc_links=[
        {"label": "Internal VPN runbook", "url": "https://wiki.example.com/vpn"},
        {"label": "Vendor guide", "url": "https://vendor.example.com/vpn"},
    ])
    docs = section(platform_page(client, "VPN"), 'class="guidance-docs"', "</p>")
    assert docs.index("Internal VPN runbook") < docs.index("Vendor guide") and docs.count("noopener noreferrer") == 2


def test_platform_heading_and_sections_in_order(client):
    html = sql_page(client)
    order = ["What good looks like on SQL Server", "Common practices", "Guides for", "References", "Runs on:"]
    present = [html.index(text) for text in order if text in html]
    assert present == sorted(present) and html.index("What good looks like on SQL Server") > 0


def test_common_practices_are_one_collapsed_section_per_category_with_counts(client):
    publish_guidance({"category": "database"}, lines={"Access": "Limit admin access.", "Recovery": "Test restores."})
    publish_control("AC", title="Database access review", categories=[Category.DATABASE], level="key")
    publish_control("CM", title="Jobs change review", categories=[Category.JOBS], level="key")
    html = sql_page(client)
    practices = section(html, 'id="practices-heading"', "</section>")
    assert practices.count("<details") == 2
    assert "<details open" not in practices and " open>" not in practices
    database = section(practices, "<details", "</details>")
    assert "category-database" in database and "<summary>Database (3)</summary>" in database
    assert database.count('class="place-row"') == AspectQuestion.objects.count()
    assert "Limit admin access." in database and "Test restores." in database
    assert "No control yet" in database and "Jobs change review" not in database
    jobs = practices[practices.index("<details", practices.index("</details>")):]
    assert "category-jobs" in jobs and "<summary>Jobs and interfaces (1)</summary>" in jobs
    assert "Jobs change review" in jobs


def test_common_practices_count_is_zero_without_guidance_or_controls(client):
    practices = section(platform_page(client, "VPN"), 'id="practices-heading"', "</section>")
    assert "<summary>Network (0)</summary>" in practices and practices.count("<details") == 1


def test_a_row_counts_once_whether_it_has_a_line_a_control_or_both(client):
    publish_guidance({"category": "database"}, lines={"Change": "Review changes.", "Logging": "Send logs to Splunk."})
    publish_control("LA", title="Log feed check", categories=[Category.DATABASE])
    publish_control("LA", title="Alerting", categories=[Category.DATABASE])
    publish_control("DR", title="Restore test", categories=[Category.DATABASE])
    assert "<summary>Database (3)</summary>" in sql_page(client)


def test_common_practices_use_category_tags_not_other_platforms_tags(client):
    publish_control("AC", [Platform.objects.get(name="Windows Server")], title="Windows only")
    assert "Windows only" not in sql_page(client)


def test_specific_considerations_show_the_platform_lines_and_directly_tagged_controls(client):
    sql = Platform.objects.get(name="SQL Server")
    publish_guidance({"category": "database"}, lines={"Access": "Limit admin access."})
    publish_guidance({"platform": sql}, tag="p", lines={"Access": "Treat sysadmin and db_owner as privileged roles."})
    tagged = publish_control("CM", [sql], title="SQL change review")
    publish_control("AC", title="Database access review", categories=[Category.DATABASE])
    specific = section(sql_page(client), 'id="specific-heading"', "</section>")
    assert specific.count('class="place-row"') == 2
    access = section(specific, ">Access</a>", "</li>")
    assert "Treat sysadmin and db_owner as privileged roles." in access and "Limit admin access." not in access
    topic_url = reverse("topics:detail", args=[AspectQuestion.objects.get(label="Access").topic.slug])
    assert f'class="place-label" href="{topic_url}">Access</a>' in section(specific, "<li", "</li>")
    assert tagged.ident in section(specific, ">Change</a>", "</li>")
    assert "Database access review" not in specific
    assert "No control yet" not in specific and "Guidance coming soon" not in specific
    assert "No platform-specific considerations yet." not in specific


@pytest.mark.usefixtures("sso")
def test_specific_considerations_empty_state_is_for_tech_risk_only():
    url = Platform.objects.get(name="SQL Server").get_absolute_url()
    edit = reverse("platforms:guidance_edit", kwargs={"slug": "sql-server"})
    tech_risk = section(As("author", "tr").get(url).content.decode(), 'id="specific-heading"', "</section>")
    assert "Specific considerations" in tech_risk
    assert '<p class="text-secondary">No platform-specific considerations yet.</p>' in tech_risk
    assert f'href="{edit}"' in tech_risk
    reader = As("reader", "ro").get(url).content.decode()
    assert "Specific considerations" not in reader and "No platform-specific considerations" not in reader


def test_platform_page_without_guidance_shows_gaps_in_common_practices(client):
    html = platform_page(client, "VPN")
    assert html.count("No control yet") == AspectQuestion.objects.count()
    assert "Guides for" not in html and "Runs on:" not in html


def test_runs_on_is_a_plain_line_at_the_bottom_linking_to_the_platform(client):
    windows = Platform.objects.get(name="Windows Server")
    html = sql_page(client)
    line = f'<p class="runs-on">Runs on: <a class="platform-chip" href="{windows.get_absolute_url()}">Windows Server</a>'
    assert line in html and html.index(line) > html.index('id="practices-heading"')
    assert "Runs on:" not in platform_page(client, "Windows Server")


def test_runs_on_is_hidden_when_the_platform_is_inactive(client):
    Platform.objects.filter(name="Windows Server").update(is_active=False)
    assert "Runs on:" not in sql_page(client)


def test_platform_references_include_category_and_platform_references_once(client):
    sql = Platform.objects.get(name="SQL Server")
    publish_guidance({"category": "database"}, references=[{"label": "Database standard", "url": "https://example.com/db"}])
    publish_guidance({"category": "jobs"}, tag="j", references=[{"label": "Database standard", "url": "https://example.com/db"}])
    publish_guidance({"platform": sql}, tag="p", references=[{"label": "SQL hardening", "url": "https://example.com/sql"}])
    refs = sql_page(client)
    refs = refs[refs.index('id="references-heading"'):]
    assert refs.index("Database standard") < refs.index("SQL hardening")
    assert refs.count("Database standard") == 1


def test_platform_guides_list_published_pages_with_section_pill(client):
    from apps.core import versioning as v
    from apps.wiki.models import Page, PageVersion
    from .support import tech_risk_pair

    sql = Platform.objects.get(name="SQL Server")
    owner, approver = tech_risk_pair("guide")
    page, version = v.create_entity(
        Page, PageVersion, owner, {"slug": "sql-admin"}, title="SQL Server admin guide", section="best_practice",
        platform=sql, owner_role="o", review_by=date(2027, 1, 1),
    )
    v.submit(version, owner)
    v.approve_and_publish(version, approver)
    html = platform_page(client, "SQL Server")
    guides = section(html, "Guides for SQL Server", "</section>")
    assert 'class="type-pill type-pill-section-best_practice">Best practices<' in guides
    assert '<a href="/guides/sql-admin/">SQL Server admin guide</a>' in guides
    assert "Guides for" not in platform_page(client, "Splunk")


def test_platform_unknown_slug_is_404(client):
    assert client.get(reverse("platforms:detail", args=["nope"])).status_code == 404


def test_library_pages_highlight_the_library_nav_which_points_home(client):
    for url in (reverse("core:home"), reverse("platforms:category", args=["jobs"]),
                Platform.objects.get(name="Splunk").get_absolute_url()):
        nav = section(get(client, url), 'aria-label="Primary"', "</nav>")
        assert_in_html('<a href="/" aria-current="page">Library</a>', nav)


def test_platform_page_query_count_is_flat(client):
    sql = Platform.objects.get(name="SQL Server")
    url = sql.get_absolute_url()
    publish_control("AC", platforms=[sql], title="First")
    small = count_queries(client, url)
    for n, prefix in enumerate(["AC", "CM", "LA", "VM"]):
        publish_control(prefix, platforms=[sql], title=f"More {n}")
        publish_control(prefix, title=f"Category {n}")
    assert count_queries(client, url) == small


def test_category_page_query_count_is_flat(client):
    sql = Platform.objects.get(name="SQL Server")
    url = reverse("platforms:category", args=["database"])
    publish_control("AC", platforms=[sql], title="First")
    small = count_queries(client, url)
    for n, prefix in enumerate(["AC", "CM", "LA", "VM"]):
        publish_control(prefix, platforms=[sql], title=f"More {n}")
    assert count_queries(client, url) == small
