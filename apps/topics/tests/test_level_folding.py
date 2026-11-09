"""Topic pages: controls sorted by level, open levels shown, the rest folded under More controls."""

import pytest
from django.urls import reverse

from apps.topics.tests.test_views import (  # noqa: F401  (fixtures and helpers shared with the topic page tests)
    access, add_control, add_risk, approver, author, html, topics,
)
from apps.wiki.tests.support import count_queries

pytestmark = pytest.mark.django_db


def add_three(access, author, approver, **place):
    for title, level in (("Helper control", "supporting"), ("Extra control", "non-key"), ("Top control", "key")):
        add_control(access, author, approver, title=title, level=level, **place)


def test_stage_list_shows_key_first_and_folds_the_rest(client, access, author, approver):
    stage = access.stages.first()
    add_three(access, author, approver, stage=stage)
    page = html(client, reverse("topics:detail", args=[access.slug]) + f"?stage={stage.pk}")
    lifecycle = page.split('id="lifecycle-view"')[1].split('id="throughout"')[0].split('id="everything-heading"')[0]
    fold = lifecycle.index("More controls (2)")
    assert lifecycle.index("Top control") < fold < lifecycle.index("Extra control") < lifecycle.index("Helper control")


def test_everything_list_folds_non_key_controls_but_keeps_risks(client, access, author, approver):
    add_three(access, author, approver)
    add_risk(access, author, approver, title="A risk")
    page = html(client, reverse("topics:detail", args=[access.slug]))
    everything = page[page.index('id="everything"'):]
    assert everything.index("Top control") < everything.index("A risk") < everything.index("More controls (2)")
    assert everything.index("More controls (2)") < everything.index("Extra control") < everything.index("Helper control")
    assert "Required for SOX" not in page


def test_throughout_lists_fold(client, access, author, approver):
    theme = access.themes.first()
    add_three(access, author, approver, theme=theme)
    page = html(client, reverse("topics:detail", args=[access.slug]))
    throughout = page.split('id="throughout"')[1].split('id="everything-heading"')[0]
    assert throughout.index("Top control") < throughout.index("More controls (2)") < throughout.index("Extra control")


def test_type_filter_controls_still_folds(client, access, author, approver):
    add_three(access, author, approver)
    page = html(client, reverse("topics:detail", args=[access.slug]) + "?type=controls")
    assert "More controls (2)" in page.split('id="everything"')[1]


def test_query_count_is_flat(client, access, author, approver):
    url = reverse("topics:detail", args=[access.slug])
    add_control(access, author, approver, title="First", level="key")
    small = count_queries(client, url)
    for n in range(4):
        add_control(access, author, approver, title=f"More {n}", level="supporting")
    assert count_queries(client, url) == small
