"""Pages must not run more queries as the number of items grows."""

import pytest
from django.urls import reverse

from apps.core.tests.support import make_user
from apps.accounts.roles import TECH_RISK
from apps.platforms.models import Platform

from .support import count_queries, make_faq, make_page

pytestmark = pytest.mark.django_db


@pytest.fixture
def people():
    return make_user("proposer", TECH_RISK), make_user("approver", TECH_RISK)


def add_pages(people, how_many, platform):
    for n in range(how_many):
        make_page(*people, title=f"Guide {how_many}-{n}", platform=platform)


def test_guides_index_query_count_is_flat(client, people):
    platform = Platform.objects.create(name="Splunk", categories=["logging"])
    add_pages(people, 2, platform)
    small = count_queries(client, reverse("wiki:index"))
    add_pages(people, 6, platform)
    assert count_queries(client, reverse("wiki:index")) == small


def test_guide_page_query_count_does_not_depend_on_other_guides(client, people):
    first = make_page(*people, title="First guide")
    small = count_queries(client, first.get_absolute_url())
    add_pages(people, 6, None)
    assert count_queries(client, first.get_absolute_url()) == small


def test_faq_page_query_count_is_flat(client, people):
    pages = [make_page(*people, title=f"Page {n}") for n in range(2)]
    make_faq(*people, related=pages, question="One?")
    small = count_queries(client, reverse("wiki:faq"))
    for n in range(5):
        make_faq(*people, related=pages, question=f"More {n}?")
    assert count_queries(client, reverse("wiki:faq")) == small
