"""Query counts stay flat as data grows; evidence rule list; Tech Risk-only edit helpers."""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As, publish, published_control, published_driver
from apps.rcm import services
from apps.rcm.models import EvidenceRule, EvidenceRuleVersion

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


def add_register_items(topic, owner, reviewer, count, start=0):
    """`count` more controls, drivers and risks, each risk linked to its own control and driver."""
    for n in range(start, start + count):
        control = published_control(topic, owner.user, reviewer.user, title=f"Control {n}")[0]
        driver = published_driver(owner.user, reviewer.user, title=f"Driver {n}")[0]
        entity, version = services.create_risk(
            owner.user, topic, title=f"Risk {n}", statement="s", owner_role="IAM"
        )
        services.set_risk_links(version, owner.user, controls=[(control, "full", "Covers it")], drivers=[driver])
        publish(version, reviewer.user)


def query_count(user, url):
    user.get(url)  # the first request signs the user in, which has its own queries
    with CaptureQueriesContext(connection) as queries:
        assert user.get(url).status_code == 200
    return len(queries)


def pages(topic):
    """URLs to measure: the explorer in both views, the matrix-driven detail pages."""
    return [
        reverse("rcm:explorer"),
        reverse("rcm:explorer") + "?view=controls",
        reverse("rcm:control", args=["MA-01"]),
        reverse("rcm:risk", args=["R-MA-01"]),
        reverse("rcm:driver", args=["RD01"]),
        reverse("rcm:evidence_rules"),
    ]


def test_query_counts_do_not_grow_with_data(owner, reviewer, access):
    add_register_items(access, owner, reviewer, 5)
    small = [query_count(owner, url) for url in pages(access)]
    add_register_items(access, owner, reviewer, 10, start=5)
    large = [query_count(owner, url) for url in pages(access)]
    assert large == small


def test_explorer_query_count_has_a_fixed_ceiling(owner, reviewer, access):
    add_register_items(access, owner, reviewer, 5)
    assert query_count(owner, reverse("rcm:explorer")) <= 20


# Evidence rule list

def make_rule(user, name, items=("x",), position=0):
    return v.create_entity(
        EvidenceRule, EvidenceRuleVersion, user, {}, name=name, applies_to="all", items=list(items), position=position
    )


def test_evidence_rule_list_shows_published_and_draft_rules(owner, reviewer):
    _, live = make_rule(owner.user, "Live rule", position=1)
    publish(live, reviewer.user)
    _, draft = make_rule(owner.user, "Draft rule", items=("a", "b"), position=2)
    html = owner.get(reverse("rcm:evidence_rules")).content.decode()
    assert html.index("Live rule") < html.index("Draft rule")
    assert reverse("rcm:evidence_rule_edit", args=[live.entity_id]) in html
    assert reverse("rcm:evidence_rule_edit", args=[draft.entity_id]) in html
    assert reverse("rcm:evidence_rule_new") in html


def test_evidence_rule_list_leaves_out_retired_rules(owner, reviewer):
    entity, version = make_rule(owner.user, "Old rule")
    publish(version, reviewer.user)
    publish(v.propose_retirement(entity, owner.user, "Not needed"), reviewer.user)
    assert "Old rule" not in owner.get(reverse("rcm:evidence_rules")).content.decode()


def test_evidence_rule_list_is_empty_state_without_rules(owner):
    assert "No evidence rules yet" in owner.get(reverse("rcm:evidence_rules")).content.decode()


def test_explorer_links_to_evidence_rules(owner):
    html = owner.get(reverse("rcm:explorer")).content.decode()
    assert f'href="{reverse("rcm:evidence_rules")}"' in html


# Permissions: every rcm edit-side page is Tech Risk only

@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_edit_side_pages_are_tech_risk_only(owner, group):
    entity, _ = make_rule(owner.user, "A rule")
    urls = [
        reverse("rcm:evidence_rules"),
        reverse("rcm:evidence_rule_new"),
        reverse("rcm:evidence_rule_edit", args=[entity.pk]),
        reverse("rcm:topic_options"),
    ]
    other = As(f"other-{group}", group)
    assert [other.get(url).status_code for url in urls] == [403] * len(urls)
    assert other.post(urls[1], {"name": "x", "applies_to": "all", "position": 0, "items": json.dumps(["x"])}).status_code == 403


def test_tech_risk_reaches_edit_side_pages(owner):
    entity, _ = make_rule(owner.user, "A rule")
    for url in (reverse("rcm:evidence_rule_edit", args=[entity.pk]), reverse("rcm:topic_options")):
        assert owner.get(url).status_code == 200
