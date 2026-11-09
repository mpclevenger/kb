"""Roles and what they may do. Change the table below to change who can do what.

A user can hold several roles; they get everything any of their roles allows.
Approving is further limited by the workflow rules: nobody approves their own proposal
(see apps/core/workflow_rules.py).
"""

from functools import wraps

from django.core.exceptions import PermissionDenied

from .roles import AUDITOR, CONTROL_OWNER, READ_ONLY, TECH_RISK

ROLES_ALLOWED = {
    "view": {TECH_RISK, CONTROL_OWNER, AUDITOR, READ_ONLY},
    "view_history": {TECH_RISK, AUDITOR},
    "propose": {TECH_RISK},
    "approve": {TECH_RISK},
    "admin": {TECH_RISK},
}


def user_roles(user):
    if user is None or not user.is_authenticated:
        return set()
    cached = getattr(user, "_trac_roles", None)
    if cached is None:
        cached = set(user.trac_roles.values_list("role", flat=True))
        if user.is_superuser:
            cached.add(TECH_RISK)
        user._trac_roles = cached
    return set(cached)


def _allowed(user, ability):
    return bool(user_roles(user) & ROLES_ALLOWED[ability])


def is_tech_risk(user):
    return TECH_RISK in user_roles(user)


def can_view(user):
    return _allowed(user, "view")


def can_view_history(user):
    return _allowed(user, "view_history")


def can_propose(user):
    return _allowed(user, "propose")


def can_approve(user):
    return _allowed(user, "approve")


def can_admin(user):
    return _allowed(user, "admin")


def permission_required_for(check):
    """View decorator: answer 403 unless `check(user)` is true, e.g. @permission_required_for(can_propose)."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def can_see_version(user, version):
    """Published versions are visible to all viewers; proposals only to Tech Risk and the proposer."""
    if version.status == "published":
        return can_view(user)
    return is_tech_risk(user) or (
        user is not None and user.is_authenticated and version.proposed_by_id == user.pk
    )
