"""Fixtures shared across the test suite.

Plain helpers live in apps/core/tests/support.py.
"""

import pytest
from django.core.management import call_command

from apps.core.tests.support import GROUPS, As, published_control, published_driver
from apps.topics.models import Topic


@pytest.fixture
def sso(settings):
    settings.AUTH_MODE = "sso"
    settings.SSO_USER_HEADER = "HTTP_X_AUTH_USER"
    settings.SSO_NAME_HEADER = "HTTP_X_AUTH_NAME"
    settings.SSO_EMAIL_HEADER = "HTTP_X_AUTH_EMAIL"
    settings.SSO_GROUPS_HEADER = "HTTP_X_AUTH_GROUPS"
    settings.SSO_GROUP_ROLE_MAP = ",".join(f"grp-{k}:{role}" for k, role in GROUPS.items())


@pytest.fixture
def topics():
    call_command("seed_topics")
    return Topic.objects


@pytest.fixture
def access(topics):
    return topics.get(id_prefix="MA")


@pytest.fixture
def other_topic(topics, access):
    return topics.exclude(pk=access.pk).first()


@pytest.fixture
def owner():
    return As("owner", "tr")


@pytest.fixture
def reviewer():
    return As("reviewer", "tr")


@pytest.fixture
def second_reviewer():
    return As("reviewer2", "tr")


@pytest.fixture
def live_control(access, owner, reviewer):
    return published_control(access, owner.user, reviewer.user, title="Review access")[0]


@pytest.fixture
def live_driver(owner, reviewer):
    return published_driver(owner.user, reviewer.user)[0]
