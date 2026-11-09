"""Checks the guide files in content/guides and explains any mistake in plain words."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.platforms.models import Platform
from apps.wiki.guide_checks import find_placeholders, guide_problems
from apps.wiki.starter_guides import GUIDES_DIR, GuideFileError, parse_guide


class Command(BaseCommand):
    help = "Check the starter guide files in content/guides and report problems in plain words."

    def add_arguments(self, parser):
        parser.add_argument("--folder", default=str(GUIDES_DIR), help="Folder of guide files (default: content/guides).")
        parser.add_argument(
            "--content-folder",
            default=str(GUIDES_DIR.parent),
            help="Folder holding controls/ and platforms/ files, also scanned for placeholder links (default: content).",
        )

    def handle(self, *args, folder, content_folder, **options):
        paths = sorted(Path(folder).glob("*.md"))
        if not paths:
            raise CommandError(f"No .md guide files found in {folder}.")
        platform_names = set(Platform.objects.values_list("name", flat=True))
        failed = 0
        for path in paths:
            try:
                problems = guide_problems(parse_guide(path), platform_names)
            except GuideFileError as error:
                problems = [str(error).removeprefix(f"{path.name}: ")]
            if problems:
                failed += 1
                self.stdout.write(self.style.ERROR(f"{path.name}"))
                for problem in problems:
                    self.stdout.write(f"  - {problem}")
            else:
                self.stdout.write(f"{path.name}: OK")
        placeholders = self.list_placeholders(paths, content_folder)
        if failed:
            raise CommandError(f"{failed} of {len(paths)} guide files have problems (see above).")
        self.stdout.write(self.style.SUCCESS(f"All {len(paths)} guide files are fine."))
        self.stdout.write(f"{placeholders} placeholder link(s) to fill in once the owning team's page exists.")

    def list_placeholders(self, guide_paths, content_folder):
        """Print every #todo- link in the guides and the controls and platforms files. Information only."""
        content = Path(content_folder)
        files = list(guide_paths) + sorted(content.glob("controls/*.yaml")) + sorted(content.glob("platforms/**/*.yaml"))
        count = 0
        for path in files:
            for text, target in find_placeholders(path.read_text(encoding="utf-8")):
                if count == 0:
                    self.stdout.write("Placeholder links to fill in:")
                count += 1
                self.stdout.write(f"  {path.name}: \"{text}\" -> {target}")
        return count
