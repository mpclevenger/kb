"""Bring the Markdown files in content/guides and the pages in the site into line with each other."""

import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from markdownify import MarkdownConverter

from apps.core import content_sync as cs
from apps.core import versioning as v
from apps.platforms.models import Platform
from apps.wiki.models import Page, PageVersion, unique_page_slug
from apps.wiki.starter_guides import GUIDES_DIR, OWNER_ROLE, split_front_matter


def _review_by():
    today = timezone.localdate()
    return today.replace(year=today.year + 1, day=min(today.day, 28))


def _same_content(version, guide, platform):
    return (version.title, version.section, version.platform, version.body) == (guide.title, guide.section, platform, guide.body)


def _platform_for(guide, notes):
    if not guide.platform:
        return None
    platform = Platform.objects.filter(name=guide.platform).first()
    if platform is None:
        notes.append(f"no platform named '{guide.platform}', so it loads without a platform")
    return platform


def sync_guide(guide, user, *, publish=False, force=False, dry_run=False):
    """Bring one guide file into the site as a draft (or publish it). Returns a cs.Outcome."""
    title = guide.title
    found = PageVersion.objects.filter(title=title).select_related("entity").order_by("-number").first()
    # A guide whose title was changed in its file is still the same guide: fall back to its file name (the page slug).
    page = found.entity if found else Page.objects.filter(slug=guide.slug).first()
    notes = []
    platform = _platform_for(guide, notes)
    suffix = f" (note: {notes[0]})" if notes else ""
    verb = "Would draft" if dry_run else "Drafted"
    if publish:
        verb = "Would publish" if dry_run else "Published"

    published = page.current() if page else None
    matches = bool(published and published.kind != v.Kind.RETIRE and _same_content(published, guide, platform))
    decision = cs.decide(page, title, guide.source_hash, force=force, site_matches_file=matches,
                         export_command="export_guides")
    if decision.kind == cs.IS_NEW:
        if not dry_run:
            version = _create(guide, user, platform)
            cs.record(version.entity, version, guide.source_hash)
            cs.finish(version, user, publish)
        return cs.Outcome(cs.NEW, f"{title}: {verb.lower()} as a new guide{suffix}.")
    if decision.kind != cs.UPDATE:
        if decision.remember and not dry_run:
            cs.record(page, published, guide.source_hash)
        return cs.Outcome(decision.outcome, decision.message)
    if dry_run:
        return cs.Outcome(cs.UPDATED, f"{title}: would propose an update from {guide.file}{suffix}.")
    content = {"title": title, "section": guide.section, "platform": platform, "body": guide.body}
    version = v.propose_change(page, user, f"Updated from content/guides/{guide.file}", **content)
    cs.record(page, version, guide.source_hash)
    cs.finish(version, user, publish)
    return cs.Outcome(cs.UPDATED, f"{title}: {'published an update' if publish else 'drafted an update'} from {guide.file}{suffix}.")


def _create(guide, user, platform):
    _, version = v.create_entity(
        Page, PageVersion, user, {"slug": unique_page_slug(guide.slug)},
        title=guide.title, section=guide.section, platform=platform, body=guide.body,
        owner_role=OWNER_ROLE, review_by=_review_by(),
    )
    return version


def sync_guides(guides, user, **options):
    cs.ensure_can_publish(options.get("publish", False))
    report = cs.Report()
    for guide in guides:
        try:
            with transaction.atomic():
                outcome = sync_guide(guide, user, **options)
        except ValidationError as error:
            outcome = cs.Outcome(cs.SKIPPED, f"{guide.title}: could not be updated: {' '.join(error.messages)}")
        report.outcomes.append(outcome)
    return report


# Export: site -> files

class _GuideConverter(MarkdownConverter):
    """HTML to Markdown. A table whose cells hold lists or paragraphs can't be written as a
    Markdown table, so it is kept as a small HTML block with a note saying why."""

    def convert_pre(self, el, text, parent_tags):
        if "mermaid" in (el.get("class") or []):
            return f"\n\n```mermaid\n{el.get_text().strip(chr(10))}\n```\n\n"
        return super().convert_pre(el, text, parent_tags)

    def convert_table(self, el, text, parent_tags):
        if el.find(["ul", "ol", "p", "br"]):
            note = ("<!-- This table is written in HTML because its cells hold more than plain text "
                    "(for example bullet lists), which a Markdown table cannot do. -->\n")
            return f"\n\n{note}{el.decode()}\n\n"
        return super().convert_table(el, text, parent_tags)


def html_to_markdown(html):
    text = _GuideConverter(heading_style="ATX", bullets="-", strong_em_symbol="*").convert(html)
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).replace("\n\n\n", "\n\n") + "\n"


def guide_file_text(version, order=None):
    header = [f"title: {version.title}", f"section: {version.section}"]
    if version.platform:
        header.append(f"platform: {version.platform.name}")
    if order is not None:
        header.append(f"order: {order}")
    return "---\n" + "\n".join(header) + "\n---\n" + html_to_markdown(version.body)


def _existing_files(directory):
    """{title: path} for the guide files already in the folder."""
    files = {}
    for path in sorted(directory.glob("*.md")):
        try:
            fields, _ = split_front_matter(path.read_text(encoding="utf-8"), path.name)
        except Exception:
            continue
        files[fields.get("title")] = (path, fields.get("order"))
    return files


def export_guides(title=None, directory=GUIDES_DIR):
    """Write the current published version of each guide to its file. Returns [(file name, 'written'|'unchanged')]."""
    existing = _existing_files(directory)
    done = []
    for page in Page.objects.order_by("slug"):
        version = page.current()
        if version is None or version.kind == v.Kind.RETIRE or (title and version.title != title):
            continue
        path, order = existing.get(version.title, (directory / f"{page.slug}.md", None))
        text = guide_file_text(version, order)
        unchanged = path.exists() and path.read_text(encoding="utf-8") == text
        if not unchanged:
            path.write_text(text, encoding="utf-8")
        cs.record(page, version, hashlib.sha256(text.encode("utf-8")).hexdigest())
        done.append((path.name, "unchanged" if unchanged else "written"))
    return done
