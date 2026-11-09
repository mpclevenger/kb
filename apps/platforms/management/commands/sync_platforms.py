"""Brings the category and platform guidance files in content/platforms into the site as drafts or proposed changes."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.commands import USER_HELP, tech_risk_user
from apps.core.content_sync import ContentSyncError, Report
from apps.platforms import guidance_files


class Command(BaseCommand):
    help = (
        "Bring the site's category and platform guidance in line with the YAML files in content/platforms. "
        "New guidance becomes a draft; changed guidance becomes a proposed change. Nothing is overwritten in place. "
        "Platforms must already exist (seed_platforms loads the catalog)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)
        parser.add_argument("--folder", help="Folder of guidance files. Defaults to content/platforms.")
        parser.add_argument("--publish", action="store_true",
                            help="Also submit and approve what this creates. Needs single-approver mode.")
        parser.add_argument("--force", action="store_true",
                            help="Replace guidance that was edited in the site since the last sync.")
        parser.add_argument("--dry-run", action="store_true", help="Say what would happen and change nothing.")

    def handle(self, *args, user, folder=None, publish=False, force=False, dry_run=False, **options):
        proposer = tech_risk_user(user)
        report = guidance_files.read_folder(folder)
        if report.problems:
            raise CommandError("Nothing was changed.\n" + "\n".join(report.problems))
        try:
            outcomes = guidance_files.sync(
                report, proposer, self.stdout.write, publish=publish, force=force, dry_run=dry_run
            )
        except ContentSyncError as error:
            raise CommandError(str(error)) from None
        verb = "Would change" if dry_run else "Done"
        self.stdout.write(f"{verb}: {Report(outcomes).counts_line()}.")
