"""Creates the three standard evidence rules as drafts on a new site."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core import versioning as v
from apps.core.commands import USER_HELP, tech_risk_user
from apps.rcm.models import EvidenceRule, EvidenceRuleVersion, RuleAppliesTo

# Sample content to get Tech Risk started, not approved guidance. Everything is saved as a
# draft; rewrite it and fill in the [to be confirmed] parts before publishing.
SAMPLE_RULES = [
    ("Before you send evidence", RuleAppliesTo.ALL, [
        "Show the full window, not a cropped section.",
        "Show the date and time.",
        "Show the system name or URL.",
        "Send the raw export, not an edited copy. If you filtered it, keep the original and note the filter.",
        "Match the period and items requested.",
    ]),
    ("A complete review record", RuleAppliesTo.DETECTIVE, [
        "What was reviewed, its source and the date it was pulled.",
        "Who reviewed it and when.",
        "What each item was checked against.",
        "A decision on every item.",
        "What happened to each flagged item, with tickets and closure dates.",
        "A sign-off.",
    ]),
    ("Where evidence lives and how long it's kept", RuleAppliesTo.ALL, [
        "Save evidence to [shared location — to be confirmed] when the control runs, not when it's requested.",
        "Keep evidence for [retention period — to be confirmed].",
        "Before a system is retired or migrated, confirm where its evidence will live.",
    ]),
]


class Command(BaseCommand):
    help = (
        "Load sample evidence rules as drafts. They are placeholders for Tech Risk to rewrite "
        "and publish. Skips any rule whose name already exists."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help=USER_HELP)

    @transaction.atomic
    def handle(self, *args, user, **options):
        proposer = tech_risk_user(user)
        for position, (name, applies_to, items) in enumerate(SAMPLE_RULES, start=1):
            if EvidenceRuleVersion.objects.filter(name=name).exists():
                self.stdout.write(f"Skipped {name}: already exists.")
                continue
            v.create_entity(
                EvidenceRule, EvidenceRuleVersion, proposer, name=name, applies_to=applies_to,
                items=items, position=position,
            )
            self.stdout.write(f"Drafted sample rule {name}.")
