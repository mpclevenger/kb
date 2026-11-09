"""Registers the shared core app with Django and connects the audit log on startup."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"

    def ready(self):
        from . import audit  # noqa: F401
