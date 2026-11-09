"""Checks that the home page is the Library and the old Library address still works."""

import pytest
from django.core.management import call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


def home(client):
    return client.get(reverse("core:home")).content.decode()


def test_home_is_the_library_at_the_site_root(client):
    html = home(client)
    assert reverse("core:home") == "/"
    assert "<h1" in html and ">Library<" in html
    assert "Start with what you run" not in html and "More ways in" not in html
    assert "data-filter-input" in html and "js/filter.js" in html
    assert html.count('class="category-card ') == 9


def test_library_url_redirects_to_home(client):
    response = client.get(reverse("platforms:index"))
    assert response.status_code == 302 and response["Location"] == "/"


def test_nav_library_and_wordmark_point_home(client):
    html = home(client)
    assert '<a class="trac-wordmark" href="/">' in html
    assert '<a href="/" aria-current="page">Library</a>' in html


def test_home_reader_without_tech_risk_role_can_open_it(sso):
    from apps.core.tests.support import As

    assert As("reader", "ro").get("/").status_code == 200
