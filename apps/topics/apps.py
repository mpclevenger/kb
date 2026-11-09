"""Registers the topics app with Django."""

from django.apps import AppConfig


class TopicsConfig(AppConfig):
    name = "apps.topics"
    label = "topics"
