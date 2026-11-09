"""Writes the site's published guides back to the files in content/guides."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.wiki.guide_sync import export_guides
from apps.wiki.starter_guides import GUIDES_DIR


class Command(BaseCommand):
    help = (
        "Write the current published version of each guide back to its file in content/guides, "
        "so edits made in the site are not lost. Run this before sync_guides if anyone edited in the site."
    )

    def add_arguments(self, parser):
        parser.add_argument("--title", help="Only export the guide with this exact title.")

        parser.add_argument("--folder", default=str(GUIDES_DIR), help="Folder to write to (default: content/guides).")

    def handle(self, *args, title, folder, **options):
        done = export_guides(title, Path(folder))
        if not done:
            raise CommandError(f"No published guide titled '{title}'." if title else "No published guides to export.")
        for name, what in done:
            self.stdout.write(f"{name}: {what}")
        written = sum(1 for _, what in done if what == "written")
        self.stdout.write(self.style.SUCCESS(f"{written} files written, {len(done) - written} already up to date."))
