"""Loads the guide files as drafts on a new site (the same as sync_guides)."""

from apps.wiki.management.commands.sync_guides import Command as SyncCommand


class Command(SyncCommand):
    help = "Load the guide files as drafts on a new site. Same as sync_guides; kept for setup_trac."
