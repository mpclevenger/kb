"""Platform and category pages: controls sorted by level, open levels shown, the rest folded."""

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.accounts.roles import TECH_RISK
from apps.core.tests.support import make_user
from apps.platforms.categories import Category
from apps.platforms.models import Platform
from apps.rcm import levels
from apps.wiki.tests.support import count_queries

from .support import publish_control

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


def make_three():
    for title, level in (("Supporting helper", "supporting"), ("Plain extra", "non-key"), ("Top control", "key")):
        publish_control("AC", title=title, categories=[Category.DATABASE], level=level)


def test_category_page_shows_open_levels_and_folds_the_rest(client):
    make_three()

    html = client.get(reverse("platforms:category", args=[Category.DATABASE.value])).content.decode()
    fold = html.index("More controls (2)")
    assert html.index("Top control") < fold < html.index("Plain extra") < html.index("Supporting helper")
    assert html.index('<p class="more-controls-level">Non-key</p>') < html.index("Plain extra")
    assert html.index('<p class="more-controls-level">Supporting</p>') < html.index("Supporting helper")
    assert "Required for SOX" not in html


def test_platform_page_folds_too_and_open_flag_comes_from_file(client, tmp_path, monkeypatch):
    make_three()
    page = Platform.objects.get(name="SQL Server").get_absolute_url()
    html = client.get(page).content.decode()
    assert html.index("Top control") < html.index("More controls (2)") < html.index("Plain extra")
    # Open the second level in levels.yaml and it moves out of the fold.
    path = tmp_path / "levels.yaml"
    path.write_text(
        "levels:\n  - {key: key, label: Key, open: true}\n  - {key: non-key, label: Non-key, open: true}\n"
        "  - {key: supporting, label: Supporting, open: false}\n"
    )
    monkeypatch.setattr(levels, "LEVELS_FILE", path)
    levels.clear_cache()
    try:
        html = client.get(page).content.decode()
        assert html.index("Top control") < html.index("Plain extra") < html.index("More controls (1)")
    finally:
        levels.clear_cache()


def test_no_fold_when_every_control_is_open(client):
    publish_control("AC", title="Only top", categories=[Category.DATABASE], level="key")
    html = client.get(Platform.objects.get(name="SQL Server").get_absolute_url()).content.decode()
    assert "Only top" in html and "More controls" not in html


def test_query_count_is_flat_with_folded_controls(client):
    url = Platform.objects.get(name="SQL Server").get_absolute_url()
    publish_control("AC", title="First", categories=[Category.DATABASE], level="key")
    small = count_queries(client, url)
    for n in range(4):
        publish_control("AC", title=f"More {n}", categories=[Category.DATABASE], level="supporting")
    assert count_queries(client, url) == small
