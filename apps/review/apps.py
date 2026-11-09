"""Registers the comments and review app with Django."""

from django.apps import AppConfig


class ReviewConfig(AppConfig):
    name = "apps.review"
    label = "review"
