"""Check the front page files in content/home."""

from django.core.management.base import BaseCommand, CommandError

from apps.core import home_files


class Command(BaseCommand):
    help = "Check the front page files (content/home). Changes nothing."

    def handle(self, *args, **options):
        problems = home_files.problems()
        if problems:
            raise CommandError("\n".join(problems))
        self.stdout.write(f"All good: the front page and {len(home_files.tools())} tool page(s).")
