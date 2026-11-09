"""check_content, sync_content and export_content: the wrapper commands over guides and controls."""

import io
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import content_sync as cs
from apps.core.tests.support import make_user
from apps.platforms import guidance_files
from apps.rcm import control_files
from apps.platforms.models import Guidance
from apps.rcm.models import ControlVersion, Driver, EngineRisk
from apps.wiki.models import PageVersion

pytestmark = pytest.mark.django_db


@pytest.fixture
def lead(db):
    call_command("seed_topics")
    call_command("seed_platforms")
    return make_user("lead", "tech_risk")


def run(name, *args, **options):
    out = io.StringIO()
    call_command(name, *args, stdout=out, stderr=io.StringIO(), **options)
    return out.getvalue()


def test_check_content_checks_guides_then_controls_with_a_summary(lead):
    out = run("check_content")
    assert out.index("Guides (content/guides)") < out.index("Risk engine drivers and risks (content/engine)") < out.index(
        "Controls and risks (content/controls)") < out.index("Platforms and guidance (content/platforms)") < out.index("Summary")
    assert "All good: 8 drivers, 2 engine risks." in out
    assert "guide files are fine" in out and "All good" in out and "guidance file(s)" in out and "All done." in out


def test_check_content_reports_both_parts_even_when_one_fails(lead, tmp_path, monkeypatch):
    (tmp_path / "bad.yaml").write_text("topic: [unclosed\n", encoding="utf-8")
    monkeypatch.setattr(control_files, "DEFAULT_FOLDER", tmp_path)
    out = io.StringIO()
    with pytest.raises(CommandError, match="Needs attention: Controls and risks"):
        call_command("check_content", stdout=out, stderr=io.StringIO())
    text = out.getvalue()
    assert "guide files are fine" in text
    assert "Guides (content/guides): OK" in text and "Controls and risks (content/controls): PROBLEMS" in text


def test_sync_content_drafts_guides_and_controls(lead):
    out = run("sync_content", user="lead")
    assert PageVersion.objects.exists() and ControlVersion.objects.exists() and Guidance.objects.exists()
    assert not PageVersion.objects.exclude(status="draft").exists()
    assert out.index("Guides (content/guides)") < out.index("Risk engine drivers and risks (content/engine)") < out.index(
        "Controls and risks (content/controls)") < out.index("Platforms and guidance (content/platforms)")
    assert Driver.objects.count() == 8 and EngineRisk.objects.count() == 2  # engine before controls
    assert "new" in out and "All done." in out


def test_sync_content_dry_run_changes_nothing(lead):
    out = run("sync_content", user="lead", dry_run=True)
    assert "Dry run, nothing changed" in out and "Would change" in out
    assert not PageVersion.objects.exists() and not ControlVersion.objects.exists() and not Guidance.objects.exists()
    assert not Driver.objects.exists() and not EngineRisk.objects.exists()


def test_sync_content_publish_needs_single_approver_mode_and_changes_nothing_otherwise(lead, settings):
    settings.ALLOW_SELF_APPROVAL = False
    with pytest.raises(CommandError, match="single-approver mode"):
        run("sync_content", user="lead", publish=True)
    assert not PageVersion.objects.exists() and not ControlVersion.objects.exists()


def test_sync_content_publishes_in_single_approver_mode(lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    run("sync_content", user="lead", publish=True)
    assert not PageVersion.objects.exclude(status="published").exists()
    assert not ControlVersion.objects.exclude(status="published").exists()
    assert not Driver.objects.get(ident="RD01").versions.exclude(status="published").exists()
    assert not Guidance.objects.get(category="database").versions.exclude(status="published").exists()


def test_sync_content_needs_a_tech_risk_user(lead):
    with pytest.raises(CommandError, match="No user named"):
        run("sync_content", user="nobody")


def test_export_content_writes_both_kinds_of_file_then_sync_finds_nothing_to_do(lead, settings, tmp_path, monkeypatch):
    settings.ALLOW_SELF_APPROVAL = True
    run("sync_content", user="lead", publish=True)
    guides, controls = tmp_path / "guides", tmp_path / "controls"
    guides.mkdir(), controls.mkdir()
    monkeypatch.setattr("apps.wiki.management.commands.export_guides.GUIDES_DIR", guides)
    monkeypatch.setattr(control_files, "DEFAULT_FOLDER", controls)
    platforms = tmp_path / "platforms"
    monkeypatch.setattr(guidance_files, "PLATFORMS_DIR", platforms)
    out = run("export_content")
    assert list(Path(guides).glob("*.md")) and list(Path(controls).glob("*.yaml"))
    assert list(platforms.glob("*.yaml")) and list((platforms / "categories").glob("*.yaml"))
    assert out.index("Controls and risks (content/controls)") < out.index("Platforms and guidance (content/platforms)")
    assert out.index("Guides (content/guides)") < out.index("Controls and risks (content/controls)")
    assert "All done." in out


def test_export_content_says_so_when_there_is_nothing_published(lead, tmp_path, monkeypatch):
    monkeypatch.setattr("apps.wiki.management.commands.export_guides.GUIDES_DIR", tmp_path)
    monkeypatch.setattr(control_files, "DEFAULT_FOLDER", tmp_path)
    monkeypatch.setattr(guidance_files, "PLATFORMS_DIR", tmp_path)
    with pytest.raises(CommandError, match="Needs attention: Guides"):
        run("export_content")


def test_decide_says_new_for_an_unknown_title():
    assert cs.decide(None, "T", "h").kind == cs.IS_NEW


def test_dev_settings_silence_only_the_open_mode_warning():
    from pathlib import Path

    from django.conf import settings

    from config.settings import base, dev

    assert dev.SILENCED_SYSTEM_CHECKS == ["trac.W002"]
    assert not getattr(base, "SILENCED_SYSTEM_CHECKS", [])
    assert "SILENCED_SYSTEM_CHECKS" not in (Path(settings.BASE_DIR) / "config/settings/prod.py").read_text(encoding="utf-8")
