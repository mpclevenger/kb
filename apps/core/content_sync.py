"""The one rulebook for bringing content files (guides, controls, risks) into the site.

How it works, in three lines: a ContentSync row beside each page, control or risk remembers which
version matched its file and the file's fingerprint (hash) at the last sync. A site edit makes a
newer published version, so it no longer matches the row, and the sync skips it instead of losing the edit.
Guide and control sync both ask `decide()` what to do; this file also holds publish handling.
"""

import hashlib
import json
from dataclasses import dataclass, field

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.core import versioning as v
from apps.core.models import ContentSync

NEW, UPDATED, UNCHANGED, SKIPPED = "new", "updated", "unchanged", "skipped"

# What decide() can answer.
IS_NEW = "new"
IS_UNCHANGED = "unchanged"
IN_PROGRESS = "in progress"
EDITED_IN_SITE = "edited in the site"
NOT_LIVE = "not live"
UPDATE = "update"

OUTCOME_FOR = {IS_NEW: NEW, IS_UNCHANGED: UNCHANGED, UPDATE: UPDATED}  # every other answer is "skipped"


class ContentSyncError(Exception):
    """A sync that cannot go ahead, with a plain message."""


@dataclass
class Decision:
    kind: str
    message: str = ""  # ready-made wording for every answer except new and update
    remember: bool = False  # unchanged, but the record is missing or stale: caller should call record()

    @property
    def outcome(self):
        return OUTCOME_FOR.get(self.kind, SKIPPED)


@dataclass
class Outcome:
    """What a sync did, or would do, to one item."""

    kind: str  # NEW, UPDATED, UNCHANGED or SKIPPED
    message: str


@dataclass
class Report:
    outcomes: list = field(default_factory=list)

    def count(self, kind):
        return sum(1 for o in self.outcomes if o.kind == kind)

    def counts_line(self):
        return ", ".join(f"{self.count(k)} {k}" for k in (NEW, UPDATED, UNCHANGED, SKIPPED))


def entry_hash(entry):
    """The fingerprint of one file entry (a dict), so a sync can tell whether it changed."""
    return hashlib.sha256(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()


def recorded(entity):
    return ContentSync.objects.filter(
        entity_type=ContentType.objects.get_for_model(entity), entity_id=entity.pk
    ).first()


def record(entity, version, source_hash):
    """Remember that `version` of `entity` now matches the file with this fingerprint."""
    ContentSync.objects.update_or_create(
        entity_type=ContentType.objects.get_for_model(entity), entity_id=entity.pk,
        defaults={"version_id": version.pk, "source_hash": source_hash, "synced_at": timezone.now()},
    )


def decide(entity, title, file_hash, *, force=False, site_matches_file=False, export_command="export_content"):
    """What a sync should do with one item. `entity` is None when the site has nothing with this title.

    `site_matches_file` is True when the published text already equals the file (a lost record is repaired).
    `export_command` is None for items that have no export (risk drivers), so the advice is only --force.
    """
    if entity is None:
        return Decision(IS_NEW)
    open_version, published = entity.open_proposal(), entity.current()
    row = recorded(entity)
    live_ids = {x.pk for x in (open_version, published) if x}
    if row and row.source_hash == file_hash and row.version_id in live_ids:
        return Decision(IS_UNCHANGED, f"{title}: unchanged.")
    if open_version:
        return Decision(IN_PROGRESS, f"{title}: a change is already in progress in the site; finish or discard it first.")
    if published is None or published.kind == v.Kind.RETIRE:
        return Decision(NOT_LIVE, f"{title}: not live in the site (retired or never published); not changed.")
    if site_matches_file:
        return Decision(IS_UNCHANGED, f"{title}: unchanged.", remember=True)
    if not force and (row is None or row.version_id != published.pk):
        advice = (
            f"Run {export_command} first to bring that edit into the file, or use --force to replace it."
            if export_command else "Use --force to replace that edit with the file."
        )
        return Decision(EDITED_IN_SITE, f"{title}: edited in the site since the file was last synced. {advice}")
    return Decision(UPDATE)


def ensure_can_publish(publish):
    """--publish approves your own change, which is only allowed in single-approver mode."""
    if publish and not settings.ALLOW_SELF_APPROVAL:
        raise ContentSyncError(
            "--publish is only allowed while single-approver mode is on (ALLOW_SELF_APPROVAL). "
            "Otherwise leave the drafts as they are: a second Tech Risk person must approve them in the site."
        )


def finish(version, user, publish):
    """Leave a synced version as a draft, or submit, approve and publish it when asked."""
    if publish:
        v.submit(version, user)
        v.approve_and_publish(version, user)
