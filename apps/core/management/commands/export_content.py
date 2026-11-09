"""Write the site's guides, controls, risks and platform guidance back to their content files in one go."""

from django.core.management.base import BaseCommand

from apps.core.commands import run_parts


class Command(BaseCommand):
    help = (
        "Write the site's published guides, controls and risks, and platform guidance, back to content/ so the files match the site. "
        "Run this before editing files if anyone changed something in the site."
    )

    def handle(self, *args, **options):
        run_parts(self, [
            ("Guides (content/guides)", "export_guides", {}),
            ("Controls and risks (content/controls)", "export_controls", {}),
            ("Platforms and guidance (content/platforms)", "export_platforms", {}),
        ])
