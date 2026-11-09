"""One command to turn an empty TRAC into a fully published demo.

Demo only: refuses to run when AUTH_MODE is sso.
"""

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserRole
from apps.accounts.roles import TECH_RISK
from apps.core import demo
from apps.core import versioning as v

AUTHOR = "demo-author"
APPROVER = "demo-approver"


def demo_user(username):
    user, _ = get_user_model().objects.get_or_create(username=username)
    UserRole.objects.get_or_create(user=user, role=TECH_RISK)
    return user


def draft_versions(author):
    """Every draft the demo author created, across all governed content."""
    for model in apps.get_models():
        if issubclass(model, v.GovernedVersion):
            yield from model.objects.filter(status=v.Status.DRAFT, proposed_by=author)


class Command(BaseCommand):
    help = (
        "Fill an empty TRAC with published demo content (topics, platforms, guides, controls, risks, "
        "risk drivers and engine risks, category and platform guidance, an FAQ). For demos and testing only: it refuses to run when AUTH_MODE is sso. "
        "Safe to run again."
    )

    def handle(self, *args, **options):
        if settings.AUTH_MODE == "sso":
            raise CommandError("load_demo is for demos only and can't run when AUTH_MODE is sso.")

        self.step("Creating demo users (demo-author and demo-approver)")
        author, approver = demo_user(AUTHOR), demo_user(APPROVER)

        self.step("Loading the content files: topics, platforms, guidance, guides, risk drivers, engine risks, controls, risks and evidence rules")
        call_command("setup_trac", user=AUTHOR, stdout=self.stdout)

        self.step("Loading an FAQ")
        self.stdout.write("Added." if demo.add_faq(author) else "Already there.")

        self.step("Publishing everything the demo author drafted")
        drafts = list(draft_versions(author))
        for version in drafts:
            v.submit(version, author)
            v.approve_and_publish(version, approver)
        self.stdout.write(f"Published {len(drafts)} item(s).")

        self.stdout.write(self.style.SUCCESS("Demo ready. Open http://127.0.0.1:8000/"))

    def step(self, text):
        self.stdout.write(self.style.MIGRATE_HEADING(text))
