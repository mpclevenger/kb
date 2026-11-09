"""Registers the guides-and-FAQ app with Django."""

from django.apps import AppConfig


class WikiConfig(AppConfig):
    name = "apps.wiki"
    label = "wiki"
