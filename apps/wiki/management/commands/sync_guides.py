"""Brings the guide files in content/guides into the site as drafts or proposed updates."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.commands import USER_HELP, tech_risk_user
from apps.core.content_sync import SKIPPED, ContentSyncError
from apps.wiki.guide_sync import sync_guides
from apps.wiki.starter_guides import GUIDES_DIR, GuideFileError, load_guides


class Command(BaseCommand):
    help = (
        "Bring the guide files in content/guides into the site: new guides become drafts, changed files become "
        "proposed updates. Nothing is overwritten without saying so."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)
        parser.add_argument("--publish", action="store_true",
                            help="Also approve and publish what is created. Only works in single-approver mode (ALLOW_SELF_APPROVAL).")
        parser.add_argument("--force", action="store_true",
                            help="Replace a guide even if it was edited in the site since the file was last synced.")
        parser.add_argument("--folder", default=str(GUIDES_DIR), help="Folder of guide files (default: content/guides).")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen and change nothing.")

    def handle(self, *args, user, publish, force, dry_run, folder, **options):
        proposer = tech_risk_user(user)
        try:
            guides = load_guides(folder)
        except GuideFileError as error:
            raise CommandError(str(error)) from None
        try:
            report = sync_guides(guides, proposer, publish=publish, force=force, dry_run=dry_run)
        except ContentSyncError as error:
            raise CommandError(str(error)) from None
        for outcome in report.outcomes:
            style = self.style.WARNING if outcome.kind == SKIPPED else str
            self.stdout.write(style(outcome.message))
        self.stdout.write(self.style.SUCCESS(
            f"{'Dry run, nothing changed. ' if dry_run else ''}{len(guides)} files: {report.counts_line()}."))
