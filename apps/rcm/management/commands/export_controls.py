"""Writes the site's published controls and risks back to the files in content/controls."""

from django.core.management.base import BaseCommand, CommandError

from apps.rcm import control_files
from apps.rcm.models import ControlVersion, RiskVersion
from apps.topics.models import Topic


class Command(BaseCommand):
    help = (
        "Write the site's published controls and risks back to content/controls/<topic>.yaml, "
        "so the files match the site. Use this before editing a file when the site has changed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--topic", help="Topic name. Defaults to every topic that has controls or risks.")
        parser.add_argument("--folder", help="Folder to write to. Defaults to content/controls.")

    def handle(self, *args, topic=None, folder=None, **options):
        topics = Topic.objects.filter(name=topic) if topic else Topic.objects.all()
        if topic and not topics:
            raise CommandError(f"No topic named '{topic}'.")
        folder = folder or control_files.DEFAULT_FOLDER
        for each in topics:
            if self._has_content(each):
                control_files.export_topic(each, folder, self.stdout.write)

    @staticmethod
    def _has_content(topic):
        return any(m.objects.filter(topic=topic, status="published").exists() for m in (ControlVersion, RiskVersion))
