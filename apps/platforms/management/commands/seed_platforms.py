"""Loads the platform catalog and risk-area questions from content/platforms/catalog.yaml into the site."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.platforms.catalog_file import CATALOG_FILE, read_catalog
from apps.platforms.models import AspectQuestion, Platform
from apps.topics.models import Topic


class Command(BaseCommand):
    help = (
        "Add the platforms and risk-area questions in content/platforms/catalog.yaml that the site does not have yet. "
        "Safe to run again: it never deletes and keeps anything already in the site (edit those in Manage)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        if not Topic.objects.exists():
            raise CommandError("Run seed_topics first; the site has no topics yet.")
        catalog = read_catalog()
        if catalog.problems:
            raise CommandError(f"Nothing was changed. Fix {CATALOG_FILE.name} (check_platforms lists the problems):\n" + "\n".join(catalog.problems))
        platforms, created = {}, set()
        for position, entry in enumerate(catalog.platforms, start=1):
            docs = entry["docs"]
            platforms[entry["name"]], was_created = Platform.objects.get_or_create(
                name=entry["name"],
                defaults={
                    "categories": entry["categories"],
                    "hosting": entry["hosting"],
                    "doc_links": [{"label": f"{entry['name']} documentation", "url": docs}] if docs else [],
                    "position": position,
                },
            )
            if was_created:
                created.add(entry["name"])
        for entry in catalog.platforms:  # linked last, so a platform may run on one listed after it
            if entry["name"] in created and entry["runs_on"]:
                Platform.objects.filter(name=entry["name"]).update(runs_on=platforms[entry["runs_on"]])
        topics = {t.id_prefix: t for t in Topic.objects.all()}
        for position, entry in enumerate(catalog.aspects, start=1):
            AspectQuestion.objects.get_or_create(
                topic=topics[entry["topic"]], label=entry["label"],
                defaults={"text": entry["question"], "position": position},
            )
        self.stdout.write(
            f"Platforms: {Platform.objects.count()}, aspect questions: {AspectQuestion.objects.count()}."
        )
