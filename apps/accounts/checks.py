"""Warnings shown by `manage.py check` when the site is set up in a risky way
(single-approver mode on, or visitors allowed to edit)."""

from django.conf import settings
from django.core.checks import Warning, register

from .roles import READ_ONLY


@register()
def self_approval_warning(app_configs, **kwargs):
    if not settings.ALLOW_SELF_APPROVAL:
        return []
    return [
        Warning(
            "Single-approver mode is on (ALLOW_SELF_APPROVAL). Turn it off once a second Tech Risk approver has access.",
            id="trac.W001",
        )
    ]


@register()
def open_mode_role_warning(app_configs, **kwargs):
    if settings.AUTH_MODE != "open" or settings.OPEN_MODE_ROLE == READ_ONLY:
        return []
    return [
        Warning(
            f"Visitors get the {settings.OPEN_MODE_ROLE} role without signing in. "
            "Set OPEN_MODE_ROLE=read_only for a shared site.",
            id="trac.W002",
        )
    ]
