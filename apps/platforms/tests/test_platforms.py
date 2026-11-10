"""Checks the platform catalog and which controls apply to which platform."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.accounts.roles import TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import make_user
from apps.platforms import selectors
from apps.platforms.models import Platform
from apps.rcm import services
from apps.rcm.models import Frequency, Method, Nature
from apps.rcm.selectors import current_controls
from apps.topics.models import Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


@pytest.fixture
def owner():
    return make_user("owner", TECH_RISK)


@pytest.fixture
def approver():
    return make_user("approver", TECH_RISK)


def control(owner, approver, topic_prefix, platforms=(), **extra):
    topic = Topic.objects.get(id_prefix=topic_prefix)
    data = dict(title="A control", why="w", owner_role="o", nature=Nature.DETECTIVE,
                method=Method.MANUAL, frequency=Frequency.QUARTERLY)
    data.update(extra)
    entity, version = services.create_control(owner, topic, **data)
    version.platforms.set(platforms)
    v.submit(version, owner)
    v.approve_and_publish(version, approver)
    return entity


def rows_by_label(platform):
    controls = selectors.applicable_controls(current_controls(), platforms=[platform])
    return {r.question.label: r for r in selectors.aspect_rows(controls, selectors.active_questions())}


def test_aspect_rows_flag_gaps(seeded, owner, approver):
    ghes = Platform.objects.get(name="GitHub Enterprise Server")
    control(owner, approver, "MA", platforms=[ghes], level="key")
    rows = rows_by_label(ghes)
    assert len(rows["Access"].controls) == 1 and rows["Access"].has_content
    assert not rows["Recovery"].controls and not rows["Recovery"].has_content


def test_applicable_controls_match_categories_or_platforms(seeded, owner, approver):
    sql = Platform.objects.get(name="SQL Server")
    by_category = control(owner, approver, "DR", categories=["database"], title="By category")
    by_platform = control(owner, approver, "MA", platforms=[sql], title="By platform")
    control(owner, approver, "MC", categories=["network"], title="Unrelated")
    controls = current_controls()
    assert {c.ident for c, _ in selectors.applicable_controls(controls, categories=["database"])} == {by_category.ident}
    assert {c.ident for c, _ in selectors.applicable_controls(controls, platforms=[sql])} == {by_platform.ident}
    both = selectors.applicable_controls(controls, categories=["database"], platforms=[sql])
    assert {c.ident for c, _ in both} == {by_category.ident, by_platform.ident}
    assert selectors.applicable_controls(controls) == []


def test_category_platforms_are_active_members_of_the_category(seeded):
    Platform.objects.filter(name="Splunk").update(is_active=False)
    names = {p.name for p in selectors.category_platforms("jobs")}
    assert names == {"Databricks", "GitHub Enterprise Server", "SQL Server", "Windows Server", "In-house job scheduler"}


def test_platforms_copied_and_locked(seeded, owner, approver):
    aws = Platform.objects.get(name="AWS")
    entity = control(owner, approver, "PI", platforms=[aws])
    draft = v.propose_change(entity, owner, "Reword")
    assert list(draft.platforms.all()) == [aws]
    with pytest.raises(v.ImmutableVersionError):
        entity.current().platforms.clear()


def test_criteria_parts_and_sox_only_validate(seeded, owner):
    topic = Topic.objects.get(id_prefix="DR")
    _, version = services.create_control(
        owner, topic, title="Backups", why="w", owner_role="o", nature=Nature.DETECTIVE,
        method=Method.AUTOMATED, frequency=Frequency.DAILY,
        categories=["database", "operating_system"],
        criteria=[
            {"name": "Backup jobs", "part": "configuration", "items": ["Jobs match the tier"]},
            {"name": "Failures", "part": "monitoring",
             "items": [{"text": "Evidence kept seven years", "sox_only": True}]},
        ],
    )
    version.full_clean()
    assert version.has_parts


@pytest.mark.parametrize("bad", [
    {"criteria": [{"name": "g", "part": "sometimes", "items": []}]},
    {"criteria": [{"name": "g", "items": [{"text": 1}]}]},
    {"categories": ["kitchen"]},
    {"steps": [{"text": "x", "part": "later"}]},
])
def test_invalid_shapes_rejected(seeded, owner, bad):
    topic = Topic.objects.get(id_prefix="DR")
    data = dict(title="t", why="w", owner_role="o", nature=Nature.DETECTIVE, method=Method.MANUAL,
                frequency=Frequency.DAILY)
    data.update(bad)
    _, version = services.create_control(owner, topic, **data)
    with pytest.raises(ValidationError):
        version.full_clean()
