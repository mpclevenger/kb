"""Checks the draft, review and publish engine: workflow, locked published text, history and retiring."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.roles import AUDITOR, CONTROL_OWNER, READ_ONLY, TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import make_user, new_widget, publish_first
from apps.core.tests.testapp.models import Widget

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return make_user("owner", TECH_RISK)


@pytest.fixture
def risk_a():
    return make_user("risk_a", TECH_RISK)


@pytest.fixture
def risk_b():
    return make_user("risk_b", TECH_RISK)


class TestCreateAndDraft:
    def test_create_makes_entity_and_draft_v1(self, owner):
        entity, version = new_widget(owner)
        assert version.number == 1
        assert version.status == v.Status.DRAFT
        assert entity.current() is None

    def test_only_tech_risk_can_propose(self):
        new_widget(make_user("tr", TECH_RISK), key="tr")
        for name, role in [("co", CONTROL_OWNER), ("ro", READ_ONLY), ("aud", AUDITOR)]:
            with pytest.raises(PermissionDenied):
                new_widget(make_user(name, role), key=name)

    def test_user_without_role_cannot_propose(self):
        with pytest.raises(PermissionDenied):
            new_widget(make_user("nobody"), key="x")

    def test_proposer_can_edit_draft(self, owner):
        _, version = new_widget(owner)
        v.update_draft(version, owner, title="Edited")
        version.refresh_from_db()
        assert version.title == "Edited"

    def test_other_user_cannot_edit_draft(self, owner, risk_a):
        _, version = new_widget(owner)
        with pytest.raises(PermissionDenied):
            v.update_draft(version, risk_a, title="Nope")

    def test_update_rejects_workflow_fields(self, owner):
        _, version = new_widget(owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.update_draft(version, owner, status=v.Status.PUBLISHED)

    def test_discard_first_draft_removes_entity(self, owner):
        entity, version = new_widget(owner)
        v.discard_draft(version, owner)
        assert not Widget.objects.filter(pk=entity.pk).exists()


class TestWorkflow:
    def test_full_flow_publishes(self, owner, risk_a):
        entity, version = publish_first(owner, risk_a)
        version.refresh_from_db()
        assert version.status == v.Status.PUBLISHED
        assert version.decided_by == risk_a
        assert entity.current() == version

    def test_self_approval_blocked(self, risk_a):
        _, version = new_widget(risk_a)
        v.submit(version, risk_a)
        with pytest.raises(PermissionDenied):
            v.approve(version, risk_a)

    def test_control_owner_cannot_approve(self, risk_a):
        _, version = new_widget(risk_a)
        v.submit(version, risk_a)
        with pytest.raises(PermissionDenied):
            v.approve(version, make_user("co", CONTROL_OWNER))

    def test_cannot_approve_a_draft(self, owner, risk_a):
        _, version = new_widget(owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.approve(version, risk_a)

    def test_cannot_publish_unapproved(self, owner, risk_a):
        _, version = new_widget(owner)
        v.submit(version, owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.publish(version, risk_a)

    def test_withdraw_returns_to_draft(self, owner):
        _, version = new_widget(owner)
        v.submit(version, owner)
        v.withdraw(version, owner)
        assert version.status == v.Status.DRAFT
        assert version.submitted_at is None

    def test_reject_requires_comment(self, owner, risk_a):
        _, version = new_widget(owner)
        v.submit(version, owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.reject(version, risk_a, "  ")
        v.reject(version, risk_a, "Objective unclear")
        assert version.status == v.Status.REJECTED
        assert version.decision_comment == "Objective unclear"

    def test_signal_fires_per_transition(self, owner, risk_a):
        seen = []

        def handler(sender, version, from_status, to_status, **kwargs):
            seen.append((from_status, to_status))

        v.version_transitioned.connect(handler)
        try:
            publish_first(owner, risk_a)
        finally:
            v.version_transitioned.disconnect(handler)
        assert seen == [
            (None, "draft"),
            ("draft", "in_review"),
            ("in_review", "approved"),
            ("approved", "published"),
        ]


class TestImmutability:
    def test_content_locked_after_submit(self, owner):
        _, version = new_widget(owner)
        v.submit(version, owner)
        version.title = "Sneaky edit"
        with pytest.raises(v.ImmutableVersionError):
            version.save()

    def test_published_version_cannot_be_deleted(self, owner, risk_a):
        _, version = publish_first(owner, risk_a)
        with pytest.raises(v.ImmutableVersionError):
            version.delete()

    def test_update_draft_refuses_after_submit(self, owner):
        _, version = new_widget(owner)
        v.submit(version, owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.update_draft(version, owner, title="Late")


class TestChanges:
    def test_change_copies_published_content(self, owner, risk_a):
        entity, _ = publish_first(owner, risk_a, body="Original body")
        draft = v.propose_change(entity, owner, "Retitle", title="New title")
        assert draft.number == 2
        assert draft.body == "Original body"
        assert draft.title == "New title"
        assert entity.current().title == "First title"

    def test_one_open_proposal_per_entity(self, owner, risk_a, risk_b):
        entity, _ = publish_first(owner, risk_a)
        v.propose_change(entity, owner, title="A")
        with pytest.raises(v.TransitionNotAllowed):
            v.propose_change(entity, risk_b, title="B")

    def test_new_publish_becomes_current(self, owner, risk_a):
        entity, first = publish_first(owner, risk_a)
        second = v.propose_change(entity, owner, title="Second")
        v.submit(second, owner)
        v.approve_and_publish(second, risk_a)
        assert entity.current() == second
        first.refresh_from_db()
        assert first.status == v.Status.PUBLISHED


class TestPointInTime:
    def test_as_of_returns_version_effective_then(self, owner, risk_a):
        entity, first = publish_first(owner, risk_a)
        before_second = timezone.now()
        second = v.propose_change(entity, owner, title="Second")
        v.submit(second, owner)
        v.approve_and_publish(second, risk_a)
        assert entity.version_as_of(before_second) == first
        assert entity.current() == second

    def test_future_effective_date_not_current_yet(self, owner, risk_a):
        entity, first = publish_first(owner, risk_a)
        future = timezone.now() + timedelta(days=30)
        second = v.propose_change(entity, owner, title="Next quarter")
        v.submit(second, owner)
        v.approve_and_publish(second, risk_a, effective_from=future)
        assert entity.current() == first
        assert entity.version_as_of(future + timedelta(seconds=1)) == second

    def test_before_first_publish_is_none(self, owner, risk_a):
        before = timezone.now() - timedelta(seconds=1)
        entity, _ = publish_first(owner, risk_a)
        assert entity.version_as_of(before) is None


class TestRetirement:
    def test_retire_flow(self, owner, risk_a):
        entity, _ = publish_first(owner, risk_a)
        retire = v.propose_retirement(entity, owner, "Superseded by W-2")
        assert retire.kind == v.Kind.RETIRE
        v.submit(retire, owner)
        v.approve_and_publish(retire, risk_a)
        assert entity.is_retired()
        assert entity.history().count() == 2

    def test_retire_needs_reason(self, owner, risk_a):
        entity, _ = publish_first(owner, risk_a)
        with pytest.raises(v.TransitionNotAllowed):
            v.propose_retirement(entity, owner, "")

    def test_cannot_retire_unpublished(self, owner):
        entity, _ = new_widget(owner)
        with pytest.raises(v.TransitionNotAllowed):
            v.propose_retirement(entity, owner, "Never used")

    def test_no_changes_after_retirement(self, owner, risk_a):
        entity, _ = publish_first(owner, risk_a)
        retire = v.propose_retirement(entity, owner, "Obsolete")
        v.submit(retire, owner)
        v.approve_and_publish(retire, risk_a)
        with pytest.raises(v.TransitionNotAllowed):
            v.propose_change(entity, owner, title="Revive")

    def test_effective_entities_excludes_retired(self, owner, risk_a):
        keep, _ = publish_first(owner, risk_a)
        gone, _ = publish_first(owner, risk_a, key="W-2")
        retire = v.propose_retirement(gone, owner, "Obsolete")
        v.submit(retire, owner)
        v.approve_and_publish(retire, risk_a)
        assert list(v.effective_entities(Widget)) == [keep]
