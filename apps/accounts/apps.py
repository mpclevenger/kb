"""Registers the sign-in and roles app with Django, and its startup checks."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        from . import checks  # noqa: F401
