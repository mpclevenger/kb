"""Brings the control and risk files in content/controls into the site as drafts or proposed changes."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.commands import USER_HELP, tech_risk_user
from apps.core.content_sync import ContentSyncError, Report
from apps.rcm import control_files


class Command(BaseCommand):
    help = (
        "Bring the site's controls and risks in line with the YAML files in content/controls. "
        "New items become drafts; changed items become proposed changes. Nothing is overwritten in place."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)
        parser.add_argument("--folder", help="Folder of .yaml files. Defaults to content/controls.")
        parser.add_argument("--publish", action="store_true",
                            help="Also submit and approve what this creates. Needs single-approver mode.")
        parser.add_argument("--force", action="store_true",
                            help="Replace controls and risks that were edited in the site since the last sync.")
        parser.add_argument("--dry-run", action="store_true", help="Say what would happen and change nothing.")

    def handle(self, *args, user, folder=None, publish=False, force=False, dry_run=False, **options):
        proposer = tech_risk_user(user)
        report = control_files.read_folder(folder)
        for warning in report.warnings:
            self.stderr.write(f"Warning: {warning}")
        if report.problems:
            raise CommandError("Nothing was changed.\n" + "\n".join(report.problems))
        try:
            outcomes = control_files.sync(
                report, proposer, self.stdout.write, publish=publish, force=force, dry_run=dry_run
            )
        except ContentSyncError as error:
            raise CommandError(str(error)) from None
        summary = Report(outcomes).counts_line()
        verb = "Would change" if dry_run else "Done"
        self.stdout.write(f"{verb}: {summary}.")
