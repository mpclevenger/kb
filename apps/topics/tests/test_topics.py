"""Checks that topics, stages and themes load and validate correctly."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.topics.models import Topic

pytestmark = pytest.mark.django_db


def test_seed_creates_topics_with_ordered_stages():
    call_command("seed_topics")
    assert Topic.objects.count() == 11
    access = Topic.objects.get(id_prefix="MA")
    assert [s.name for s in access.stages.all()] == ["Roles to permissions", "Provisioning", "Periodic review", "Deprovisioning"]
    assert access.themes.filter(name="Privileged access").exists()


def test_seed_is_idempotent_and_keeps_edits():
    call_command("seed_topics")
    access = Topic.objects.get(id_prefix="MA")
    access.summary = "Edited by Tech Risk"
    access.save()
    call_command("seed_topics")
    assert Topic.objects.count() == 11
    assert Topic.objects.get(id_prefix="MA").summary == "Edited by Tech Risk"
    assert access.stages.count() == 4


def test_prefix_must_be_capitals():
    topic = Topic(name="Bad", id_prefix="ab", icon="key")
    with pytest.raises(ValidationError):
        topic.full_clean()


def test_slug_generated():
    topic = Topic.objects.create(name="New topic", id_prefix="NT", icon="key")
    assert topic.slug == "new-topic"


def test_seed_sets_summaries_only_when_empty():
    call_command("seed_topics")
    assert all(t.summary for t in Topic.objects.all())
    assert "BCP team" in Topic.objects.get(id_prefix="DR").summary
    Topic.objects.filter(id_prefix="MA").update(summary="")
    Topic.objects.filter(id_prefix="MC").update(summary="Edited")
    call_command("seed_topics")
    assert Topic.objects.get(id_prefix="MA").summary.startswith("Who can get into")
    assert Topic.objects.get(id_prefix="MC").summary == "Edited"


def test_stage_or_theme_not_both():
    from types import SimpleNamespace

    from apps.topics.validation import check_stage_or_theme

    call_command("seed_topics")
    access = Topic.objects.get(id_prefix="MA")
    change = Topic.objects.get(id_prefix="MC")
    stage, theme = access.stages.first(), access.themes.first()
    ok = SimpleNamespace(topic_id=access.pk, stage_id=None, stage=None, theme_id=theme.pk, theme=theme)
    check_stage_or_theme(ok)
    both = SimpleNamespace(topic_id=access.pk, stage_id=stage.pk, stage=stage, theme_id=theme.pk, theme=theme)
    with pytest.raises(ValidationError):
        check_stage_or_theme(both)
    wrong = SimpleNamespace(topic_id=change.pk, stage_id=None, stage=None, theme_id=theme.pk, theme=theme)
    with pytest.raises(ValidationError):
        check_stage_or_theme(wrong)


@pytest.mark.django_db
def test_old_id_prefixes_move_to_the_firms_codes_with_every_issued_id():
    from django.core.management import call_command

    from apps.core.tests.support import make_user
    from apps.rcm import services
    from apps.rcm.models import Control, IdSequence, Risk

    call_command("seed_topics")
    access = Topic.objects.get(id_prefix="MA")
    access.id_prefix = "AC"
    access.save()
    IdSequence.objects.filter(key__in=["MA", "R-MA"]).delete()
    user = make_user("owner", "tech_risk")
    control, _ = services.create_control(user, access, title="Quarterly access review")
    risk, _ = services.create_risk(user, access, title="Leavers keep access")
    assert (control.ident, risk.ident) == ("AC-01", "R-AC-01")

    call_command("seed_topics")
    assert Topic.objects.get(pk=access.pk).id_prefix == "MA"
    assert Control.objects.get(pk=control.pk).ident == "MA-01"
    assert Risk.objects.get(pk=risk.pk).ident == "R-MA-01"
    next_control, _ = services.create_control(user, Topic.objects.get(pk=access.pk), title="Second")
    assert next_control.ident == "MA-02"
    call_command("seed_topics")  # safe to run again
    assert Control.objects.get(pk=control.pk).ident == "MA-01"


@pytest.mark.django_db
def test_job_items_move_from_platforms_to_operations_with_new_ids():
    from django.core.management import call_command

    from apps.core.tests.support import make_user
    from apps.rcm import services
    from apps.rcm.models import Control, ControlVersion, Risk
    from apps.topics.models import Theme

    call_command("seed_topics")
    platforms = Topic.objects.get(id_prefix="PI")
    old_theme = Theme.objects.create(topic=platforms, name="Job scheduling and monitoring", position=9)
    user = make_user("owner", "tech_risk")
    job, _ = services.create_control(user, platforms, title="Access to the scheduler is limited", theme=old_theme)
    risk, _ = services.create_risk(user, platforms, title="Scheduler access is too broad", theme=old_theme)
    baseline, _ = services.create_control(user, platforms, title="Servers are built to a documented baseline")

    call_command("seed_topics")
    operations = Topic.objects.get(id_prefix="OP")
    assert Control.objects.get(pk=job.pk).ident == "OP-01"
    assert Risk.objects.get(pk=risk.pk).ident == "R-OP-01"
    version = ControlVersion.objects.get(entity=job)
    assert version.topic == operations and version.theme.topic == operations
    assert Control.objects.get(pk=baseline.pk).ident.startswith("PI-")
    assert not Theme.objects.filter(pk=old_theme.pk).exists()
    call_command("seed_topics")  # safe to run again
    assert Control.objects.get(pk=job.pk).ident == "OP-01"
