"""Shortcuts the platform tests use to build published controls and guidance."""

from apps.accounts.roles import TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import make_user
from apps.platforms.models import AspectQuestion, Guidance, GuidanceVersion
from apps.rcm import services
from apps.rcm.models import Frequency, Method, Nature
from apps.topics.models import Topic


def tech_risk_pair(tag):
    return make_user(f"proposer {tag}", TECH_RISK), make_user(f"approver {tag}", TECH_RISK)


def publish_control(prefix, platforms=(), title="A control", **extra):
    owner, approver = tech_risk_pair(title)
    data = dict(title=title, why="w", owner_role="o", nature=Nature.DETECTIVE, method=Method.MANUAL,
                frequency=Frequency.QUARTERLY)
    data.update(extra)
    entity, version = services.create_control(owner, Topic.objects.get(id_prefix=prefix), **data)
    version.platforms.set(platforms)
    v.submit(version, owner)
    v.approve_and_publish(version, approver)
    return entity


def question(label):
    return AspectQuestion.objects.get(label=label)


def publish_guidance(target, tag="g", intro="", lines=None, references=()):
    """Create and publish guidance for {"category": key} or {"platform": platform}. `lines` maps question label to text."""
    owner, approver = tech_risk_pair(tag)
    lines = [{"question": question(label).pk, "text": text} for label, text in (lines or {}).items()]
    entity, version = v.create_entity(
        Guidance, GuidanceVersion, owner, target, intro=intro, lines=lines, references=list(references)
    )
    v.submit(version, owner)
    v.approve_and_publish(version, approver)
    return entity
