"""Retiring an item: Tech Risk asks with a reason, a second Tech Risk member approves."""

import pytest
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As
from apps.rcm.models import EvidenceRule, EvidenceRuleVersion
from apps.wiki.tests.support import make_page

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


def retire_path(entity):
    return reverse("workflow:retire", args=[ContentType.objects.get_for_model(entity).pk, entity.pk])


@pytest.fixture
def page(owner, reviewer):
    return make_page(owner.user, reviewer.user, title="Old guide", section="build")


def test_detail_page_shows_retire_button_to_tech_risk_only(page, owner):
    assert retire_path(page) in owner.get(page.get_absolute_url()).content.decode()
    reader = As("reader", "ro")
    assert retire_path(page) not in reader.get(page.get_absolute_url()).content.decode()


def test_other_roles_cannot_open_the_form(page):
    for group in ("co", "aud", "ro"):
        assert As(f"u-{group}", group).get(retire_path(page)).status_code == 403


def test_reason_is_required(page, owner):
    response = owner.post(retire_path(page), {"reason": "  "})
    assert response.status_code == 200
    assert "A reason is required" in response.content.decode()
    assert page.open_proposal() is None


def test_retirement_goes_to_review_then_takes_effect_when_approved(page, owner, reviewer):
    response = owner.post(retire_path(page), {"reason": "Replaced by the new guide"})
    proposal = page.open_proposal()
    assert proposal.kind == v.Kind.RETIRE and proposal.status == v.Status.IN_REVIEW
    assert response.url == f"{page.get_absolute_url()}?version={proposal.number}"
    assert not page.is_retired()

    # The proposer can't approve their own retirement.
    with pytest.raises(PermissionDenied):
        v.approve_and_publish(proposal, owner.user)

    v.approve_and_publish(proposal, reviewer.user)
    assert page.is_retired()
    assert "Old guide" not in reviewer.get(reverse("wiki:index")).content.decode()
    retired_page = reviewer.get(page.get_absolute_url()).content.decode()
    assert "Retired" in retired_page and "Replaced by the new guide" in retired_page
    assert retire_path(page) not in retired_page


def test_no_retire_button_while_a_change_is_in_progress(page, owner):
    v.propose_change(page, owner.user, title="Old guide, revised")
    assert retire_path(page) not in owner.get(page.get_absolute_url()).content.decode()


def test_evidence_rule_list_offers_retire_for_published_rules(owner, reviewer):
    rule, version = v.create_entity(
        EvidenceRule, EvidenceRuleVersion, owner.user, {},
        name="Screenshots", position=1, items=["Show the date"],
    )
    html = owner.get(reverse("rcm:evidence_rules")).content.decode()
    assert retire_path(rule) not in html  # still a draft

    v.submit(version, owner.user)
    v.approve_and_publish(version, reviewer.user)
    assert retire_path(rule) in owner.get(reverse("rcm:evidence_rules")).content.decode()

    response = owner.post(retire_path(rule), {"reason": "No longer needed"})
    assert response.url.startswith(reverse("rcm:evidence_rule_edit", args=[rule.pk]))
