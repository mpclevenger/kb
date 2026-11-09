"""Registers a tiny made-up app used only by the tests of the draft and approval engine."""

from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "apps.core.tests.testapp"
    label = "core_testapp"
