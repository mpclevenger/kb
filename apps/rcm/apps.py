"""Registers the risks-and-controls app with Django."""

from django.apps import AppConfig


class RcmConfig(AppConfig):
    name = "apps.rcm"
    label = "rcm"
    verbose_name = "Risks and controls"
