"""The category and platform guidance files: checking, syncing and exporting."""

import io
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import versioning as v
from apps.core.content_sync import recorded
from apps.core.tests.support import make_user
from apps.platforms import guidance_files
from apps.platforms.catalog_file import PLATFORMS_DIR
from apps.platforms.models import Guidance, GuidanceVersion

pytestmark = pytest.mark.django_db

DATABASE = """\
category: database
intro: >
  Databases hold the data.
  Keep access narrow.
practices:
  Access: |
    - Named administrators only
    - Reviewed every year
  Change: Review changes before release.
references:
  - label: CIS benchmark
    link: https://example.com/cis
"""

SQL_SERVER = """\
platform: SQL Server
considerations:
  access: |
    - Treat sysadmin as privileged
"""


@pytest.fixture
def lead(db):
    call_command("seed_topics")
    call_command("seed_platforms")
    return make_user("lead", "tech_risk")


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "categories").mkdir()
    (tmp_path / "categories" / "database.yaml").write_text(DATABASE, encoding="utf-8")
    (tmp_path / "sql-server.yaml").write_text(SQL_SERVER, encoding="utf-8")
    return tmp_path


@pytest.fixture
def single(settings):
    settings.ALLOW_SELF_APPROVAL = True


def run(name, *args, **options):
    out = io.StringIO()
    call_command(name, *args, stdout=out, stderr=io.StringIO(), **options)
    return out.getvalue()


def sync(folder, **options):
    return run("sync_platforms", folder=str(folder), **{"user": "lead", **options})


def edit(folder, name, old, new):
    path = Path(folder) / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def site_edit(user, guidance):
    draft = v.propose_change(guidance, user, "Edited in the site", intro="Edited in the site.")
    v.submit(draft, user)
    v.approve_and_publish(draft, user)


# ---- reading and checking ----

def problems(folder):
    return guidance_files.read_folder(folder).problems


def test_good_files_are_read(lead, folder):
    report = guidance_files.read_folder(folder)
    assert report.problems == []
    database, sql = report.items
    assert database.title == "Database guidance" and database.target == {"category": "database"}
    assert database.intro == "Databases hold the data. Keep access narrow."
    assert [line["text"] for line in database.lines] == ["- Named administrators only\n- Reviewed every year", "Review changes before release."]
    assert database.references == [{"label": "CIS benchmark", "url": "https://example.com/cis"}]
    assert sql.title == "SQL Server guidance" and sql.lines[0]["text"] == "- Treat sysadmin as privileged"


def test_unknown_label_is_named_with_the_file(lead, folder):
    edit(folder, "sql-server.yaml", "access:", "acess:")
    [message] = problems(folder)
    assert message.startswith("sql-server.yaml: 'acess' under considerations isn't an aspect label. Use: Access,")


def test_unknown_category_is_named_with_the_file(lead, folder):
    edit(folder, "categories/database.yaml", "category: database", "category: databse")
    [message] = problems(folder)
    assert message.startswith("database.yaml: 'category' is 'databse', which isn't a category. Use one of: application, database")


def test_unknown_platform_is_named_with_the_file(lead, folder):
    edit(folder, "sql-server.yaml", "SQL Server", "Oracle")
    [message] = problems(folder)
    assert message.startswith("sql-server.yaml: 'platform' is 'Oracle', which isn't a platform on this site. Platforms:")


def test_bad_yaml_is_reported_in_plain_words(lead, folder):
    (folder / "sql-server.yaml").write_text("platform: [unclosed\n", encoding="utf-8")
    assert problems(folder) == ["sql-server.yaml: the file isn't valid YAML near line 2. Check the indentation and colons."]


@pytest.mark.parametrize("old, new, fragment", [
    ("  Change: Review changes before release.", "  Change:", "'Change' under practices has no text"),
    ("  Change: Review", "  access: Review", "'access' is listed twice"),
    ("references:\n  - label: CIS benchmark\n    link: https://example.com/cis", "references:\n  - label: CIS\n    link: example.com", "the link must start with https://"),
    ("intro:", "intr:", "'intr' isn't a known field"),
])
def test_other_mistakes_get_plain_messages(lead, folder, old, new, fragment):
    edit(folder, "categories/database.yaml", old, new)
    [message] = problems(folder)
    assert message.startswith("database.yaml: ") and fragment in message


def test_two_files_for_the_same_platform_are_refused(lead, folder):
    (folder / "sql-server2.yaml").write_text(SQL_SERVER, encoding="utf-8")
    assert problems(folder) == ["sql-server2.yaml: there is more than one file for SQL Server guidance."]


def test_the_catalog_is_not_read_as_a_platform_file(lead, folder):
    (folder / "catalog.yaml").write_text("platforms: []\naspects: []\n", encoding="utf-8")
    assert problems(folder) == []


def test_check_platforms_reports_and_exits(lead, folder, capsys):
    (folder / "catalog.yaml").write_text((PLATFORMS_DIR / "catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    call_command("check_platforms", folder=str(folder))
    assert "All good: 12 platforms and 12 questions in the catalog, 2 guidance file(s)." in capsys.readouterr().out
    edit(folder, "sql-server.yaml", "access:", "acess:")
    with pytest.raises(SystemExit):
        call_command("check_platforms", folder=str(folder))
    assert "Problem: sql-server.yaml" in capsys.readouterr().out


def test_check_platforms_flags_banned_wording(lead, folder, capsys):
    (folder / "catalog.yaml").write_text((PLATFORMS_DIR / "catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    edit(folder, "sql-server.yaml", "Treat sysadmin as privileged", "Treat sysadmin as a standard login")
    with pytest.raises(SystemExit):
        call_command("check_platforms", folder=str(folder))
    assert 'sql-server.yaml: the text contains "standard"' in capsys.readouterr().out


def test_sync_refuses_to_start_when_a_file_has_a_problem(lead, folder):
    edit(folder, "sql-server.yaml", "access:", "acess:")
    with pytest.raises(CommandError, match="Nothing was changed"):
        sync(folder)
    assert not Guidance.objects.exists()


@pytest.mark.skipif(not (PLATFORMS_DIR / "categories").exists(), reason="the platform content files aren't there yet")
def test_the_shipped_platform_files_are_valid(lead, capsys):
    call_command("check_platforms")
    assert "All good" in capsys.readouterr().out


# ---- syncing ----

def test_new_guidance_becomes_drafts(lead, folder):
    out = sync(folder)
    assert "Created a draft: Database guidance." in out and "Created a draft: SQL Server guidance." in out
    assert "2 new, 0 updated, 0 unchanged, 0 skipped." in out
    database = GuidanceVersion.objects.get(entity__category="database")
    assert database.status == "draft" and database.intro == "Databases hold the data. Keep access narrow."
    assert len(database.lines) == 2 and database.references[0]["url"] == "https://example.com/cis"
    assert GuidanceVersion.objects.get(entity__platform__name="SQL Server").lines[0]["text"].startswith("- Treat")


def test_second_sync_says_unchanged(lead, folder):
    sync(folder)
    out = sync(folder)
    assert "Database guidance: unchanged." in out and "0 new, 0 updated, 2 unchanged, 0 skipped." in out


def test_reformatting_a_file_does_not_count_as_a_change(lead, folder):
    sync(folder)
    edit(folder, "categories/database.yaml", "intro: >\n  Databases hold the data.\n  Keep access narrow.", "intro: Databases hold the data. Keep access narrow.")
    assert "2 unchanged" in sync(folder)


def test_a_changed_file_becomes_a_proposal(lead, folder, single):
    sync(folder, publish=True)
    edit(folder, "categories/database.yaml", "Reviewed every year", "Reviewed twice a year")
    out = sync(folder)
    assert "Proposed a change: Database guidance." in out and "1 updated, 1 unchanged" in out
    draft = GuidanceVersion.objects.get(entity__category="database", status="draft")
    assert draft.number == 2 and "twice a year" in draft.lines[0]["text"]
    assert draft.change_summary == "Updated from content/platforms/database.yaml"
    assert recorded(draft.entity).version_id == draft.pk


def test_open_proposal_blocks_the_update(lead, folder):
    sync(folder)
    edit(folder, "categories/database.yaml", "Reviewed every year", "Reviewed twice a year")
    out = sync(folder)
    assert "Database guidance: a change is already in progress in the site; finish or discard it first." in out
    assert GuidanceVersion.objects.filter(entity__category="database").count() == 1


def test_site_edits_block_the_sync_until_exported_or_forced(lead, folder, single):
    sync(folder, publish=True)
    site_edit(lead, Guidance.objects.get(category="database"))
    edit(folder, "categories/database.yaml", "Reviewed every year", "Reviewed twice a year")
    out = sync(folder)
    assert "Database guidance: edited in the site since the file was last synced. Run export_platforms first" in out
    assert not GuidanceVersion.objects.filter(status="draft").exists()
    assert "Proposed a change: Database guidance." in sync(folder, force=True)
    assert GuidanceVersion.objects.get(status="draft").intro == "Databases hold the data. Keep access narrow."


def test_publish_is_allowed_in_single_approver_mode(lead, folder, single):
    sync(folder, publish=True)
    assert not GuidanceVersion.objects.exclude(status="published").exists()


def test_publish_is_blocked_otherwise(lead, folder, settings):
    settings.ALLOW_SELF_APPROVAL = False
    with pytest.raises(CommandError, match="single-approver mode"):
        sync(folder, publish=True)
    assert not Guidance.objects.exists()


def test_dry_run_changes_nothing_and_says_what_would_happen(lead, folder, single):
    out = sync(folder, dry_run=True)
    assert "Would create a draft: Database guidance." in out and "Would change: 2 new" in out
    assert not Guidance.objects.exists()
    sync(folder, publish=True)
    edit(folder, "categories/database.yaml", "Reviewed every year", "Reviewed twice a year")
    assert "Would propose a change: Database guidance." in sync(folder, dry_run=True)
    assert not GuidanceVersion.objects.filter(status="draft").exists()


def test_site_text_that_already_matches_the_file_is_repaired_not_changed(lead, folder, single):
    sync(folder, publish=True)
    recorded(Guidance.objects.get(category="database")).delete()
    assert "Database guidance: unchanged." in sync(folder)
    assert not GuidanceVersion.objects.filter(status="draft").exists()


# ---- exporting ----

def test_export_writes_files_that_sync_as_unchanged(lead, folder, single, tmp_path_factory):
    sync(folder, publish=True)
    site_edit(lead, Guidance.objects.get(category="database"))
    out_folder = tmp_path_factory.mktemp("exported")
    out = run("export_platforms", folder=str(out_folder))
    assert "Wrote categories/database.yaml." in out and "Wrote sql-server.yaml." in out
    written = (out_folder / "categories" / "database.yaml").read_text(encoding="utf-8")
    assert "intro: >\n  Edited in the site.\n" in written and "  Access: |\n    - Named administrators only\n    - Reviewed every year\n" in written
    assert "references:\n  - label: CIS benchmark\n    link: https://example.com/cis" in written
    assert "0 new, 0 updated, 2 unchanged" in sync(out_folder)


def test_export_keeps_the_comments_at_the_top_of_a_file(lead, folder, single):
    sync(folder, publish=True)
    path = folder / "sql-server.yaml"
    path.write_text("# Notes for the maintainer\n\n" + SQL_SERVER, encoding="utf-8")
    run("export_platforms", folder=str(folder))
    assert path.read_text(encoding="utf-8").startswith("# Notes for the maintainer\n\nplatform: SQL Server\n")


def test_export_skips_unpublished_guidance(lead, folder, tmp_path_factory):
    sync(folder)
    out_folder = tmp_path_factory.mktemp("exported")
    assert "0 guidance file(s) written." in run("export_platforms", folder=str(out_folder))
    assert not list(out_folder.iterdir())
