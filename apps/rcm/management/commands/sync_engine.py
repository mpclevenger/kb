"""Brings the risk engine's drivers and risks into the site."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.commands import USER_HELP, tech_risk_user
from apps.core.content_sync import ContentSyncError, Report
from apps.rcm import engine_files


class Command(BaseCommand):
    help = (
        "Bring the site in line with content/engine and content/drivers/drivers.json. Drivers (RD01 and so on) "
        "become drafts or proposed changes; the engine's risks are replaced by the new copy. "
        "Missing drivers.json entries are added."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)
        parser.add_argument("--publish", action="store_true",
                            help="Also submit and approve what this creates. Needs single-approver mode.")
        parser.add_argument("--force", action="store_true",
                            help="Replace drivers that were edited in the site since the last sync.")
        parser.add_argument("--dry-run", action="store_true", help="Say what would happen and change nothing.")

    def handle(self, *args, user, publish=False, force=False, dry_run=False, **options):
        proposer = tech_risk_user(user)
        report = engine_files.read_engine()
        for warning in report.warnings:
            self.stderr.write(f"Warning: {warning}")
        if report.problems:
            raise CommandError("Nothing was changed.\n" + "\n".join(report.problems))
        try:
            outcomes = engine_files.sync(
                report, proposer, self.stdout.write, publish=publish, force=force, dry_run=dry_run
            )
        except ContentSyncError as error:
            raise CommandError(str(error)) from None
        verb = "Would change" if dry_run else "Done"
        self.stdout.write(f"{verb}: drivers {Report(outcomes).counts_line()}.")
