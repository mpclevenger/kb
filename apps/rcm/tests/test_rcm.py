"""Checks the basics of controls and risks: IDs, fields and how they link."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command

from apps.accounts.roles import TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import make_user
from apps.rcm import selectors, services
from apps.rcm.models import Coverage, IdSequence, Nature, Method, Frequency
from apps.topics.models import Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def topics():
    call_command("seed_topics")
    return Topic.objects


@pytest.fixture
def access(topics):
    return topics.get(id_prefix="AC")


@pytest.fixture
def owner():
    return make_user("owner", TECH_RISK)


@pytest.fixture
def approver():
    return make_user("approver", TECH_RISK)


def control_fields(**extra):
    data = dict(
        title="Quarterly user access review",
        why="Catches access that drifted.",
        owner_role="Identity and Access",
        nature=Nature.DETECTIVE,
        method=Method.MANUAL,
        frequency=Frequency.QUARTERLY,
        criteria=[{"name": "The review", "items": ["Every user has a decision."]}],
        steps=[{"role": "Owner", "text": "Review the list.", "evidence": "Signed review"}],
    )
    data.update(extra)
    return data


def publish(version, proposer, approver):
    v.submit(version, proposer)
    v.approve_and_publish(version, approver)
    return version


def published_control(access, owner, approver, **extra):
    entity, version = services.create_control(owner, access, **control_fields(**extra))
    publish(version, owner, approver)
    return entity


def published_risk(access, owner, approver, controls=(), **extra):
    entity, version = services.create_risk(
        owner, access, title="Leaver keeps access", statement="Access not removed.", owner_role="IAM", **extra
    )
    services.set_risk_links(version, owner, controls=controls)
    publish(version, owner, approver)
    return entity


class TestIds:
    def test_control_ids_use_topic_prefix(self, access, owner):
        first, _ = services.create_control(owner, access, **control_fields())
        second, _ = services.create_control(owner, access, **control_fields())
        assert (first.ident, second.ident) == ("AC-01", "AC-02")

    def test_risk_ids(self, access, owner):
        risk, _ = services.create_risk(owner, access, title="r", statement="s", owner_role="o")
        assert risk.ident == "R-AC-01"

    def test_ids_never_reused_after_discard(self, access, owner):
        entity, version = services.create_control(owner, access, **control_fields())
        v.discard_draft(version, owner)
        again, _ = services.create_control(owner, access, **control_fields())
        assert again.ident == "AC-02"
        assert IdSequence.objects.get(key="AC").last == 2


class TestControl:
    def test_publish_and_read_current(self, access, owner, approver):
        control = published_control(access, owner, approver)
        assert control.current().criteria[0]["name"] == "The review"

    def test_stage_must_belong_to_topic(self, access, topics, owner):
        other_stage = topics.get(id_prefix="CM").stages.first()
        _, version = services.create_control(owner, access, **control_fields(stage=other_stage))
        with pytest.raises(ValidationError):
            version.full_clean()

    def test_bad_criteria_shape_rejected(self, access, owner):
        _, version = services.create_control(owner, access, **control_fields(criteria=["loose text"]))
        with pytest.raises(ValidationError):
            version.full_clean()


class TestRiskLinks:
    def test_links_are_versioned_with_the_risk(self, access, owner, approver):
        control = published_control(access, owner, approver)
        risk = published_risk(access, owner, approver, controls=[(control, Coverage.FULL, "Removes leavers")])
        draft = v.propose_change(risk, owner, "Reword")
        assert draft.control_links.get().rationale == "Removes leavers"
        assert risk.current().control_links.count() == 1

    def test_links_locked_after_submit(self, access, owner, approver):
        control = published_control(access, owner, approver)
        risk = published_risk(access, owner, approver, controls=[(control, Coverage.FULL, "Reason")])
        link = risk.current().control_links.get()
        link.rationale = "changed"
        with pytest.raises(v.ImmutableVersionError):
            link.save()

    def test_link_needs_reason(self, access, owner, approver):
        control = published_control(access, owner, approver)
        _, version = services.create_risk(owner, access, title="r", statement="s", owner_role="o")
        with pytest.raises(v.TransitionNotAllowed):
            services.set_risk_links(version, owner, controls=[(control, Coverage.FULL, " ")])

    def test_only_proposer_sets_links(self, access, owner, approver):
        _, version = services.create_risk(owner, access, title="r", statement="s", owner_role="o")
        with pytest.raises(PermissionDenied):
            services.set_risk_links(version, approver)


class TestMatrix:
    def test_coverage_states(self, access, owner, approver):
        full = published_control(access, owner, approver)
        part = published_control(access, owner, approver, title="Partial one")
        covered = published_risk(access, owner, approver, controls=[(full, Coverage.FULL, "a")])
        partial = published_risk(access, owner, approver, controls=[(part, Coverage.PARTIAL, "b")])
        unmapped = published_risk(access, owner, approver)
        states = {row.risk: row.coverage for row in selectors.risk_control_matrix()}
        assert states == {covered: "covered", partial: "partial", unmapped: "unmapped"}

    def test_retired_control_drops_out_of_coverage(self, access, owner, approver):
        control = published_control(access, owner, approver)
        risk = published_risk(access, owner, approver, controls=[(control, Coverage.FULL, "a")])
        retire = v.propose_retirement(control, owner, "Replaced")
        publish(retire, owner, approver)
        row = next(r for r in selectors.risk_control_matrix() if r.risk == risk)
        assert row.coverage == "unmapped"

    def test_unlinked_controls(self, access, owner, approver):
        linked = published_control(access, owner, approver)
        lonely = published_control(access, owner, approver, title="Nobody links me")
        published_risk(access, owner, approver, controls=[(linked, Coverage.FULL, "a")])
        assert [c for c, _ in selectors.unlinked_controls(selectors.current_controls(), selectors.risk_control_matrix())] == [lonely]

    def test_drafts_not_in_matrix(self, access, owner):
        services.create_risk(owner, access, title="r", statement="s", owner_role="o")
        assert selectors.risk_control_matrix() == []


class TestSegregationAndRules:
    def test_rule_applies_by_nature(self, access, owner, approver):
        from apps.rcm.models import EvidenceRule, EvidenceRuleVersion, rule_applies

        _, rule = v.create_entity(EvidenceRule, EvidenceRuleVersion, owner, name="Complete review record",
                                  items=["Population and source"], applies_to="detective")
        detective = services.create_control(owner, access, **control_fields())[1]
        preventive = services.create_control(owner, access, **control_fields(nature=Nature.PREVENTIVE))[1]
        assert rule_applies(rule, detective) and not rule_applies(rule, preventive)
