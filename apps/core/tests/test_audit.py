"""Checks that every approval step is logged, the log cannot be altered, and only the right people see history."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts.roles import AUDITOR, CONTROL_OWNER, READ_ONLY, TECH_RISK
from apps.core import versioning as v
from apps.core.models import AuditEvent
from apps.core.tests.support import make_user, new_widget, publish_first
from apps.core.tests.testapp.models import Widget

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return make_user("owner", TECH_RISK)


@pytest.fixture
def approver():
    return make_user("approver", TECH_RISK)


def test_every_transition_is_logged(owner, approver):
    entity, _ = publish_first(owner, approver)
    events = list(AuditEvent.for_entity(entity))
    assert [(e.from_status, e.to_status) for e in events] == [
        ("", "draft"),
        ("draft", "in_review"),
        ("in_review", "approved"),
        ("approved", "published"),
    ]
    assert events[0].actor == owner
    assert events[2].actor == approver


def test_reject_comment_is_logged(owner, approver):
    entity, version = new_widget(owner)
    v.submit(version, owner)
    v.reject(version, approver, "Needs an owner")
    assert AuditEvent.for_entity(entity).last().comment == "Needs an owner"


def test_events_cannot_be_changed_or_deleted(owner, approver):
    entity, _ = publish_first(owner, approver)
    event = AuditEvent.for_entity(entity).first()
    event.comment = "rewritten"
    with pytest.raises(TypeError):
        event.save()
    with pytest.raises(TypeError):
        event.delete()
    with pytest.raises(TypeError):
        AuditEvent.objects.all().update(comment="x")
    with pytest.raises(TypeError):
        AuditEvent.objects.all().delete()


def history_url(entity):
    return reverse(
        "core:history",
        args=[ContentType.objects.get_for_model(Widget).pk, entity.pk],
    )


@pytest.mark.parametrize(
    "role,status", [(TECH_RISK, 200), (AUDITOR, 200), (CONTROL_OWNER, 403), (READ_ONLY, 403)]
)
def test_history_page_access(client, owner, approver, role, status, settings):
    settings.AUTH_MODE = "sso"
    settings.SSO_GROUP_ROLE_MAP = f"grp:{role}"
    entity, _ = publish_first(owner, approver)
    response = client.get(
        history_url(entity), HTTP_X_AUTH_USER="viewer", HTTP_X_AUTH_GROUPS="grp"
    )
    assert response.status_code == status
    if status == 200:
        assert b"approved" in response.content


def test_history_rejects_non_governed_models(client, db):
    response = client.get(
        reverse("core:history", args=[ContentType.objects.get_for_model(AuditEvent).pk, 1])
    )
    assert response.status_code == 404
