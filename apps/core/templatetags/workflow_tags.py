"""Lets page templates ask what state a draft is in and which buttons to show."""

from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.accounts.permissions import can_approve

from .. import workflow_rules
from ..versioning import Status

register = template.Library()


@register.simple_tag
def workflow_state(version, user):
    """What `user` may do with `version` right now. The rules live in workflow_rules.py."""
    if version is None or not getattr(user, "is_authenticated", False):
        return {"any": False}
    allowed = workflow_rules.allowed_actions(version, user)
    is_own_proposal_in_review = version.status == Status.IN_REVIEW and version.proposed_by_id == user.pk
    return {
        "ctype_id": ContentType.objects.get_for_model(version).pk,
        "can_submit": "submit" in allowed,
        "can_withdraw": "withdraw" in allowed,
        "can_decide": "approve" in allowed,
        "needs_other_approver": is_own_proposal_in_review and can_approve(user) and not settings.ALLOW_SELF_APPROVAL,
        "self_approval_on": settings.ALLOW_SELF_APPROVAL,
        "today": timezone.localdate().isoformat(),
        "any": bool(allowed & {"submit", "withdraw", "approve"}),
    }
