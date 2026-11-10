"""Shared, non-fixture test helpers.

Fixtures live in the conftest files. Plain helpers that test modules import by name
live here.
"""

import itertools
import json

from django.contrib.auth import get_user_model
from django.test import Client

from apps.accounts.models import UserRole
from apps.core import versioning as v
from apps.core.tests.testapp.models import Widget, WidgetVersion
from apps.rcm import services
from apps.rcm.models import Driver, Frequency, Method, Nature

GROUPS = {"tr": "tech_risk", "co": "control_owner", "ro": "read_only", "aud": "auditor"}


def make_user(username, *roles):
    user = get_user_model().objects.create(username=username)
    for role in roles:
        UserRole.objects.create(user=user, role=role)
    return get_user_model().objects.get(pk=user.pk)


def new_widget(user, key="W-1", **content):
    content.setdefault("title", "First title")
    return v.create_entity(Widget, WidgetVersion, user, {"key": key}, **content)


def publish_first(proposer, approver, **content):
    entity, version = new_widget(proposer, **content)
    v.submit(version, proposer)
    v.approve_and_publish(version, approver)
    return entity, version


class As:
    """A browser signed in through the SSO headers, with the role given by `group`."""

    def __init__(self, username, group="co"):
        User = get_user_model()
        self.username = username
        self.client = Client()
        self.headers = {
            "HTTP_X_AUTH_USER": username,
            "HTTP_X_AUTH_GROUPS": f"grp-{group}",
        }
        self.user = User.objects.get_or_create(username=username)[0]
        UserRole.objects.get_or_create(user=self.user, role=GROUPS[group])
        self.user = User.objects.get(pk=self.user.pk)

    def get(self, url, data=None, **extra):
        return self.client.get(url, data or {}, **self.headers, **extra)

    def post(self, url, data=None, **extra):
        return self.client.post(url, data or {}, **self.headers, **extra)


def anonymous():
    return Client()


_new_ids = itertools.count(1)


def control_post(topic, stage=None, **over):
    data = {
        "ident": f"T-C-{next(_new_ids):03d}",
        "title": "Quarterly review of user access",
        "topic": topic.pk,
        "stage": stage.pk if stage else "",
        "owner_role": "Identity and Access",
        "review_by": "2027-11-01",
        "performer_role": "",
        "nature": "detective",
        "method": "manual",
        "frequency": "quarterly",
        "level": "non-key",
        "why": "Catches access that drifted.",
        "applies_when": json.dumps(["You approve access", ""]),
        "criteria": json.dumps(
            [{"name": "The review", "items": ["Every user has a decision.", "  "]}, {"name": "", "items": []}]
        ),
        "steps": json.dumps(
            [
                {"role": "Owner", "text": "Review the list.", "evidence": "Signed review"},
                {"role": "", "text": "", "evidence": ""},
            ]
        ),
    }
    data.update(over)
    return data


def publish(version, approver_user):
    v.submit(version, version.proposed_by)
    v.approve_and_publish(version, approver_user)
    version.refresh_from_db()
    return version


def published_control(topic, proposer, approver, **content):
    base = dict(
        title="Existing control",
        why="Because.",
        owner_role="Ops",
        nature="detective",
        method="manual",
        frequency="monthly",
        criteria=[{"name": "A", "items": ["one"]}],
        steps=[{"role": "R", "text": "Do it", "evidence": ""}],
        applies_when=["Always"],
    )
    base.update(content)
    entity, version = services.create_control(proposer, topic, **base)
    return entity, publish(version, approver)


def risk_post(topic, **over):
    data = {
        "ident": f"T-R-{next(_new_ids):03d}",
        "title": "Leavers keep access",
        "topic": topic.pk,
        "stage": "",
        "owner_role": "Identity and Access",
        "review_by": "2027-11-01",
        "statement": "People who leave could still sign in.",
        "controls": "[]",
    }
    data.update(over)
    return data


def driver_fields(**extra):
    data = dict(
        title="Legacy systems without central sign-in",
        description="Some systems keep their own user accounts.",
        owner_role="Head of Infrastructure",
    )
    data.update(extra)
    return data


def published_driver(proposer, approver, ident=None, **content):
    """A published driver. Without an ident it takes the next free RD id (RD01, RD02 ...)."""
    ident = ident or f"RD{Driver.objects.count() + 1:02d}"
    entity, version = services.create_driver(proposer, ident, **driver_fields(**content))
    return entity, publish(version, approver)


def control_fields(**extra):
    data = dict(
        title="Quarterly user access review",
        why="Catches access that drifted.",
        owner_role="Identity and Access",
        nature=Nature.DETECTIVE,
        method=Method.MANUAL,
        frequency=Frequency.QUARTERLY,
        applies_when=["The system holds financial data."],
        criteria=[{"name": "The review", "items": ["Every user has a decision."]}],
        steps=[{"role": "Owner", "text": "Review the list.", "evidence": "Signed review"}],
    )
    data.update(extra)
    return data
