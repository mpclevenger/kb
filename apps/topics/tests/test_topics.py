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
