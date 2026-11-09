"""Registers the shared look-and-feel app with Django."""

from django.apps import AppConfig


class UiConfig(AppConfig):
    name = "apps.ui"
    label = "ui"
