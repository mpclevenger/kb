"""Loads the starting topics, with their stages and themes, into a new site."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.rcm.prefixes import move_to_topic, rename_prefix
from apps.topics.models import Stage, Theme, Topic

SUMMARIES = {
    "Access management": (
        "Who can get into your systems, what they can do once inside, and how that stays appropriate over time. It covers mapping roles to permissions, then granting, reviewing and removing access. Most teams start here, because other controls depend on it."
    ),
    "Change management": (
        "How changes to applications, infrastructure and data move from request to production with the right approvals, review and testing. It covers emergency changes, segregation of duties and direct database changes. Done well, you can show that only reviewed and tested changes reached production."
    ),
    "Logging and alerting": (
        "What your systems record, how you know the logging is still on, and what happens when an alert fires. It covers turning logging on and evidencing it, noticing when feeds stop or configuration changes, and triaging and closing alerts. Logs only help if someone actively checks that they are still arriving."
    ),
    "Vulnerability and patching": (
        "How you find weaknesses in your software and systems, decide what to fix first, and prove the fix worked. It also covers exceptions and risk acceptance, and software that no longer receives vendor updates. Recommended fix timelines are set by severity and BCP tier."
    ),
    "Platforms and infrastructure": (
        "The shared platforms your applications run on, in the cloud and on-premises, such as AWS, Azure, Kubernetes, Active Directory, Databricks and SQL Server. It sets the baseline for provisioning, configuring, monitoring and decommissioning a platform. Each platform page asks a plain technical question for every risk topic."
    ),
    "Operations and jobs": (
        "The scheduled jobs and data transfers your systems depend on, wherever they run: in an application, in SQL Server, in the in-house scheduler or on a platform. It covers how job changes are approved, who can change the scheduler, how failures are caught and fixed, and how you show data transfers are complete."
    ),
    "IT disaster recovery": (
        "How IT recovery is planned, backed up, tested and carried out after a serious disruption. This topic covers IT disaster recovery only; business continuity, meaning how the business keeps operating, sits with the BCP team. Recovery targets and test cadence depend on the application's BCP tier."
    ),
    "Networking": (
        "How network access and exposure are controlled, including VPN access and network scanning. Stages and controls for this topic are still being defined."
    ),
    "Third parties": (
        "How you choose, contract with, monitor and exit vendors that provide technology or handle your data. Vendor risk is owned by a separate team; Tech Risk reviews the risks and controls shown here. This topic is a draft proposal and may change as that team reviews it."
    ),
    "Data protection": (
        "How you know what data you hold, where it lives and how it moves, and how you protect it from collection to disposal. It covers classification, data flow mapping, protection, retention and disposal, and key management. The data governance team owns this topic; this is a draft proposal for them."
    ),
    "Designing your controls": (
        "For teams that design and build their own controls. Your team owns the control: you start from the risk, design and document it, and then review the proposal with Tech Risk and Internal Audit before you run it. Your control draft in TRAC is your design proposal."
    ),
}

# The firm's own ID codes replaced the first ones. Topics still on an old prefix are moved over, with
# every control and risk ID already issued (CM-01 becomes MC-01). Safe to run again.
PREFIX_RENAMES = {"AC": "MA", "CM": "MC"}

# Items that moved to another topic (by title). An existing site moves them, with new IDs. Safe to run again.
TOPIC_MOVES = [
    ("PI", "OP", [
        "Changes to scheduled jobs go through change control",
        "Job failures are monitored, investigated and resolved",
        "Access to the scheduler is limited",
        "Interface and data transfer completeness",
        "Scheduled jobs are changed without approval",
        "Job failures go unnoticed or unresolved",
        "Scheduler access is too broad",
        "Data transfers into financial systems are incomplete or inaccurate",
    ], ["Job scheduling and monitoring", "Interfaces and data transfers"]),
]

TOPICS = [
    ("Access management", "MA", "key",
     ["Roles to permissions", "Provisioning", "Periodic review", "Deprovisioning"],
     ["Privileged access", "Service accounts", "Segregation of duties", "Authentication"]),
    ("Change management", "MC", "git-branch",
     ["Request and approve", "Build and review", "Test", "Release", "Monitor"],
     ["Emergency changes", "Segregation of duties", "Direct database changes"]),
    ("Logging and alerting", "LA", "file-search",
     ["Configure and evidence", "Keep it on", "Triage alerts", "Resolve and close"],
     ["BCP tiering", "Failover"]),
    ("Vulnerability and patching", "VM", "bug",
     ["Scan", "Prioritize", "Remediate and verify"],
     ["Exceptions and risk acceptance", "End-of-life software"]),
    ("Platforms and infrastructure", "PI", "cloud",
     ["Provision", "Configure and evidence", "Monitor drift", "Decommission"],
     ["Asset inventory", "Infrastructure as code"]),
    ("Operations and jobs", "OP", "clock",
     [],
     ["Job scheduling and monitoring", "Interfaces and data transfers"]),
    ("IT disaster recovery", "DR", "lifebuoy",
     ["Plan", "Back up and restore", "Test recovery", "Invoke and recover"],
     ["BCP tiering", "Third-party dependencies", "Backup access"]),
    ("Networking", "NW", "network",
     [],
     ["VPN", "Network scanning"]),
    ("Third parties", "TP", "building",
     ["Select and assess", "Contract", "Monitor", "Exit"],
     ["SOC report review", "Complementary user entity controls", "Concentration risk"]),
    ("Data protection", "DP", "lock",
     ["Inventory and classify", "Map data flows", "Protect", "Retain and dispose"],
     ["Test environments and test data", "Key management"]),
    ("Designing your controls", "CD", "checklist",
     ["Start with the risk", "Design the control", "Build and document", "Review with Tech Risk and Internal Audit", "Run and improve"],
     ["Scoping by category", "Reports and data used in controls", "Evidence practices", "Automate where you can"]),
]


class Command(BaseCommand):
    help = "Create the approved topics, lifecycle stages and themes. Safe to run again; existing names are kept."

    @transaction.atomic
    def handle(self, *args, **options):
        for old, new in PREFIX_RENAMES.items():
            if Topic.objects.filter(id_prefix=old).exists():
                renamed = rename_prefix(old, new)
                self.stdout.write(f"ID prefix {old} is now {new} ({renamed} IDs changed).")
        created = 0
        for position, (name, prefix, icon, stages, themes) in enumerate(TOPICS, start=1):
            topic, was_created = Topic.objects.get_or_create(
                name=name, defaults={"id_prefix": prefix, "icon": icon, "position": position}
            )
            created += was_created
            if not topic.summary and name in SUMMARIES:
                topic.summary = SUMMARIES[name]
                topic.save(update_fields=["summary"])
            if not topic.stages.exists():
                Stage.objects.bulk_create(
                    Stage(topic=topic, name=s, position=i) for i, s in enumerate(stages, start=1)
                )
            for i, theme in enumerate(themes, start=1):
                Theme.objects.get_or_create(topic=topic, name=theme, defaults={"position": i})
        for old, new, titles, themes in TOPIC_MOVES:
            moved = move_to_topic(old, new, titles, themes)
            if moved:
                self.stdout.write(f"Moved {moved} controls and risks from {old} to {new}.")
        self.stdout.write(f"Topics created: {created}. Total topics: {Topic.objects.count()}.")
