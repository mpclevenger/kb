"""One command to fill a new, empty TRAC with its starting content.

Safe to run again: each step skips anything that already exists. Guides and evidence
rules are created as drafts, so a second Tech Risk member must approve them before
anyone else sees them.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.commands import USER_HELP, tech_risk_user

# Run in this order: platforms need topics, and guidance and controls need both topics and platforms.
# Drivers come before controls and risks because TRAC risks link to drivers.
STEPS = [
    ("Topics, stages and themes", "seed_topics", False),
    ("Platforms, categories and aspect questions", "seed_platforms", False),
    ("Category and platform guidance from content files (drafts)", "sync_platforms", True),
    ("Risk drivers and engine risks from the engine files (drivers as drafts)", "sync_engine", True),
    ("Controls and risks from content files (drafts)", "sync_controls", True),
    ("Starter guides (drafts)", "seed_guides", True),
    ("Sample evidence rules (drafts)", "seed_evidence_rules", True),
]


class Command(BaseCommand):
    help = "Load TRAC's starting content: topics, platforms, category and platform guidance, risk drivers and engine risks, starter controls and risks, starter guides and sample evidence rules."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)

    def handle(self, *args, user, **options):
        tech_risk_user(user)  # fail before changing anything
        for label, command, needs_user in STEPS:
            self.stdout.write(self.style.MIGRATE_HEADING(label))
            call_command(command, **({"user": user} if needs_user else {}), stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Starting content loaded. Guides and evidence rules are drafts until approved."))
