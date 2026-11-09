"""Checks the platform catalog and the category and platform guidance files, and explains any mistake in plain words."""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.platforms import guidance_files
from apps.platforms.catalog_file import PLATFORMS_DIR, read_catalog
from apps.wiki.guide_checks import file_wording_problems


class Command(BaseCommand):
    help = (
        "Check content/platforms (the catalog and the guidance files) without changing anything. "
        "Exits with 1 if any file has a problem."
    )

    def add_arguments(self, parser):
        parser.add_argument("--folder", help="Folder to check. Defaults to content/platforms.")

    def handle(self, *args, folder=None, **options):
        folder = folder or PLATFORMS_DIR
        catalog = read_catalog(Path(folder) / "catalog.yaml")
        report = guidance_files.read_folder(folder)
        problems = catalog.problems + report.problems + file_wording_problems(sorted(Path(folder).glob("**/*.yaml")))
        for problem in problems:
            self.stdout.write(f"Problem: {problem}")
        if problems:
            self.stdout.write(f"{len(problems)} problem(s) found. Fix them and run this again.")
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(
            f"All good: {len(catalog.platforms)} platforms and {len(catalog.aspects)} questions in the catalog, "
            f"{len(report.items)} guidance file(s)."))
