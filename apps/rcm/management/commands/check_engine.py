"""Checks the risk engine's files and drivers.json and explains any mistake in plain words."""

import sys

from django.core.management.base import BaseCommand

from apps.rcm import engine_files


class Command(BaseCommand):
    help = (
        "Check content/engine (driver_mapping.yaml and risks/*.yaml) and content/drivers/drivers.json without "
        "changing anything. Exits with 1 if any file has a problem."
    )

    def handle(self, *args, **options):
        report = engine_files.read_engine()
        warnings = [*report.warnings, *engine_files.unknown_trac_risks(report)]
        if report.missing_entries:
            warnings.append(f"drivers.json has no entry yet for {len(report.missing_entries)} driver(s); sync_engine adds them.")
        for warning in warnings:
            self.stdout.write(f"Warning: {warning}")
        for problem in report.problems:
            self.stdout.write(f"Problem: {problem}")
        if report.problems:
            self.stdout.write(f"{len(report.problems)} problem(s) found. Fix them and run this again.")
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(
            f"All good: {len(report.drivers)} drivers, {len(report.risks)} engine risks."
        ))
