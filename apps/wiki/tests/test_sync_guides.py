"""manage.py sync_guides, export_guides and seed_guides (files in content/guides <-> pages in the site)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import versioning as v
from apps.core.content_sync import recorded
from apps.core.models import ContentSync
from apps.wiki.models import Page, PageVersion
from apps.wiki.starter_guides import load_guides, parse_guide

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

HELP_LINE = "If you're unsure, Tech Risk can help."
TITLE = "Sample guide"


def write(folder, text="First version.", title=TITLE, name="sample-guide.md", extra=""):
    (folder / name).write_text(f"---\ntitle: {title}\nsection: build\n{extra}---\n{text}\n\n{HELP_LINE}\n", encoding="utf-8")


def sync(owner, folder, capsys, *flags):
    call_command("sync_guides", "--user", owner.username, "--folder", str(folder), *flags)
    return capsys.readouterr().out


def versions():
    return list(PageVersion.objects.filter(title=TITLE).order_by("number"))


def edit_in_site(editor, approver, body="<p>Edited in the site.</p>"):
    page = Page.objects.get(slug="sample-guide")
    version = v.propose_change(page, editor.user, "Site edit", body=body)
    v.submit(version, editor.user)
    v.approve_and_publish(version, approver.user)


@pytest.fixture
def folder(tmp_path):
    write(tmp_path)
    return tmp_path


def test_new_guide_becomes_a_draft_and_is_remembered(folder, owner, capsys):
    out = sync(owner, folder, capsys)
    (version,) = versions()
    assert version.status == v.Status.DRAFT and version.entity.slug == "sample-guide"
    assert recorded(version.entity).version_id == version.pk
    assert f"{TITLE}: drafted as a new guide." in out and "1 new, 0 updated, 0 unchanged, 0 skipped" in out


def test_running_again_with_the_same_file_changes_nothing(folder, owner, capsys):
    sync(owner, folder, capsys)
    out = sync(owner, folder, capsys)
    assert f"{TITLE}: unchanged." in out and len(versions()) == 1


def test_a_changed_file_proposes_an_update_and_leaves_the_published_text_alone(folder, owner, reviewer, capsys):
    sync(owner, folder, capsys)
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    write(folder, "Second version.")
    out = sync(owner, folder, capsys)
    first_after, second = versions()
    assert first_after.status == v.Status.PUBLISHED and "First version." in first_after.body
    assert second.status == v.Status.DRAFT and "Second version." in second.body
    assert second.change_summary == "Updated from content/guides/sample-guide.md"
    assert f"{TITLE}: drafted an update from sample-guide.md." in out
    assert f"{TITLE}: unchanged." in sync(owner, folder, capsys) and len(versions()) == 2


def test_an_open_proposal_in_the_site_blocks_the_update(folder, owner, capsys):
    sync(owner, folder, capsys)
    write(folder, "Second version.")
    out = sync(owner, folder, capsys)
    assert f"{TITLE}: a change is already in progress in the site; finish or discard it first." in out
    assert len(versions()) == 1 and "1 skipped" in out


def test_a_site_edit_blocks_the_update_until_exported_or_forced(folder, owner, reviewer, capsys):
    sync(owner, folder, capsys)
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    edit_in_site(reviewer, owner)
    write(folder, "Second version.")
    out = sync(owner, folder, capsys)
    assert (f"{TITLE}: edited in the site since the file was last synced. Run export_guides first to bring that edit "
            "into the file, or use --force to replace it.") in out
    assert len(versions()) == 2

    out = sync(owner, folder, capsys, "--force")
    assert len(versions()) == 3 and "Second version." in versions()[2].body and "drafted an update" in out


def test_a_site_edit_never_carries_the_file_hash(folder, owner, reviewer, capsys):
    sync(owner, folder, capsys)
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    edit_in_site(reviewer, owner)
    assert recorded(first.entity).version_id == first.pk and versions()[1].status == v.Status.PUBLISHED


def test_a_page_with_no_sync_record_but_the_same_text_counts_as_unchanged(folder, owner, reviewer, capsys):
    sync(owner, folder, capsys)
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    ContentSync.objects.all().delete()
    out = sync(owner, folder, capsys)
    assert f"{TITLE}: unchanged." in out and ContentSync.objects.count() == 1


def test_publish_is_refused_unless_single_approver_mode_is_on(folder, owner, capsys):
    with pytest.raises(CommandError, match="second Tech Risk person must approve"):
        sync(owner, folder, capsys, "--publish")
    assert not versions()


def test_publish_publishes_new_and_updated_guides_in_single_approver_mode(folder, owner, settings, capsys):
    settings.ALLOW_SELF_APPROVAL = True
    out = sync(owner, folder, capsys, "--publish")
    assert [x.status for x in versions()] == [v.Status.PUBLISHED] and "published as a new guide" in out
    write(folder, "Second version.")
    out = sync(owner, folder, capsys, "--publish")
    assert [x.status for x in versions()] == [v.Status.PUBLISHED] * 2 and "published an update" in out
    assert "Second version." in Page.objects.get(slug="sample-guide").current().body


def test_dry_run_reports_and_changes_nothing(folder, owner, settings, capsys):
    out = sync(owner, folder, capsys, "--dry-run")
    assert f"{TITLE}: would draft as a new guide." in out and "Dry run, nothing changed" in out
    assert not versions() and not ContentSync.objects.exists()
    settings.ALLOW_SELF_APPROVAL = True
    sync(owner, folder, capsys, "--publish")
    write(folder, "Second version.")
    out = sync(owner, folder, capsys, "--dry-run")
    assert "would propose an update" in out and len(versions()) == 1


def test_a_broken_file_stops_the_run_naming_the_file(folder, owner, capsys):
    (folder / "broken.md").write_text("no header", encoding="utf-8")
    with pytest.raises(CommandError, match="broken.md"):
        sync(owner, folder, capsys)
    assert not versions()


def test_seed_guides_is_the_same_command(folder, owner):
    call_command("seed_guides", user=owner.username, folder=str(folder))
    assert len(versions()) == 1


# export_guides

@pytest.fixture
def published_real_guides(owner, reviewer, topics):
    call_command("seed_platforms")
    call_command("sync_guides", user=owner.username)
    for version in PageVersion.objects.all():
        v.submit(version, owner.user)
        v.approve_and_publish(version, reviewer.user)


def test_export_then_sync_reports_every_real_guide_unchanged(published_real_guides, owner, tmp_path, capsys):
    call_command("export_guides", folder=str(tmp_path))
    assert len(list(tmp_path.glob("*.md"))) == len(load_guides())
    out = sync(owner, tmp_path, capsys)
    assert f"{len(load_guides())} files: 0 new, 0 updated, {len(load_guides())} unchanged, 0 skipped" in out


def test_exported_files_read_back_as_the_same_guides(published_real_guides, tmp_path):
    call_command("export_guides", folder=str(tmp_path))
    for original in load_guides():
        again = parse_guide(tmp_path / f"{original.slug}.md")
        assert (again.title, again.section, again.platform) == (original.title, original.section, original.platform)
        assert again.body == original.body, original.title


def test_export_brings_a_site_edit_into_the_file_and_marks_it_synced(folder, owner, reviewer, capsys):
    sync(owner, folder, capsys)
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    edit_in_site(reviewer, owner, "<h2>New card</h2><p>Edited <strong>in</strong> the site.</p>")
    call_command("export_guides", "--title", TITLE, folder=str(folder))
    text = (folder / "sample-guide.md").read_text(encoding="utf-8")
    assert "## New card" in text and "Edited **in** the site." in text and text.startswith("---\ntitle: Sample guide\n")
    out = sync(owner, folder, capsys)
    assert f"{TITLE}: unchanged." in out and len(versions()) == 2


def test_export_keeps_the_order_line_and_skips_unpublished_guides(folder, owner, reviewer, capsys):
    write(folder, extra="order: 7\n")
    sync(owner, folder, capsys)
    with pytest.raises(CommandError, match="No published guides"):
        call_command("export_guides", folder=str(folder))
    first = versions()[0]
    v.submit(first, owner.user)
    v.approve_and_publish(first, reviewer.user)
    edit_in_site(reviewer, owner)
    call_command("export_guides", folder=str(folder))
    assert "order: 7\n" in (folder / "sample-guide.md").read_text(encoding="utf-8")


def test_export_keeps_a_table_with_lists_as_html(published_real_guides, tmp_path):
    call_command("export_guides", "--title", "Initiative lifecycle", folder=str(tmp_path))
    text = (tmp_path / "initiative-lifecycle.md").read_text(encoding="utf-8")
    assert "<!-- This table is written in HTML" in text and "<ul><li>" in text
    assert "## Stage 2: Build and configure" in text and "#### Item 3:" in text
