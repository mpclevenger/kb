"""Writes the site's published category and platform guidance back to the files in content/platforms."""

from django.core.management.base import BaseCommand

from apps.platforms import guidance_files


class Command(BaseCommand):
    help = (
        "Write the site's published guidance back to content/platforms (categories/<category>.yaml and "
        "<platform>.yaml) so the files match the site. Use this before editing a file when the site has changed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--folder", help="Folder to write to. Defaults to content/platforms.")

    def handle(self, *args, folder=None, **options):
        written = guidance_files.export(folder, self.stdout.write)
        self.stdout.write(self.style.SUCCESS(f"{len(written)} guidance file(s) written."))
