"""Bring the guide files, the risk engine files, the control and risk files, then the platform files into the site in one go."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.commands import USER_HELP, run_parts, tech_risk_user
from apps.core.content_sync import ContentSyncError, ensure_can_publish


class Command(BaseCommand):
    help = (
        "Sync content/guides, the risk engine files (content/engine), content/controls, then content/platforms, into the site. New items become drafts and changes become "
        "proposed updates. Add --dry-run first to see what would happen."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)
        parser.add_argument("--publish", action="store_true",
                            help="Also approve and publish. Only works in single-approver mode (ALLOW_SELF_APPROVAL).")
        parser.add_argument("--force", action="store_true",
                            help="Replace items that were edited in the site since the last sync.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen and change nothing.")

    def handle(self, *args, user, publish, force, dry_run, **options):
        tech_risk_user(user)
        try:
            ensure_can_publish(publish)
        except ContentSyncError as error:
            raise CommandError(str(error)) from None
        shared = {"user": user, "publish": publish, "force": force, "dry_run": dry_run}
        run_parts(self, [
            ("Guides (content/guides)", "sync_guides", shared),
            ("Risk engine drivers and risks (content/engine)", "sync_engine", shared),
            ("Controls and risks (content/controls)", "sync_controls", shared),
            ("Platforms and guidance (content/platforms)", "sync_platforms", shared),
        ])
