"""Checks the control and risk files in content/controls and explains any mistake in plain words."""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.rcm import control_files
from apps.wiki.guide_checks import file_wording_problems


class Command(BaseCommand):
    help = "Check the YAML files in content/controls without changing anything. Exits with 1 if any file has a problem."

    def add_arguments(self, parser):
        parser.add_argument("--folder", help="Folder of .yaml files. Defaults to content/controls.")

    def handle(self, *args, folder=None, **options):
        report = control_files.read_folder(folder)
        report.problems += file_wording_problems(sorted(Path(folder or control_files.DEFAULT_FOLDER).glob("*.yaml")))
        for warning in report.warnings:
            self.stdout.write(f"Warning: {warning}")
        for problem in report.problems:
            self.stdout.write(f"Problem: {problem}")
        if report.problems:
            self.stdout.write(f"{len(report.problems)} problem(s) found. Fix them and run this again.")
            sys.exit(1)
        controls = sum(len(p.controls) for p in report.plans)
        risks = sum(len(p.risks) for p in report.plans)
        self.stdout.write(self.style.SUCCESS(f"All good: {len(report.plans)} file(s), {controls} controls, {risks} risks."))
