"""Check the guide files, the risk engine files, the control and risk files, and the platform files in one go."""

from django.core.management.base import BaseCommand

from apps.core.commands import run_parts


class Command(BaseCommand):
    help = "Check every content file (guides, risk engine, controls and risks, then platforms) and report problems in plain words. Changes nothing."

    def handle(self, *args, **options):
        run_parts(self, [
            ("Guides (content/guides)", "check_guides", {}),
            ("Risk engine drivers and risks (content/engine)", "check_engine", {}),
            ("Controls and risks (content/controls)", "check_controls", {}),
            ("Platforms and guidance (content/platforms)", "check_platforms", {}),
        ])
