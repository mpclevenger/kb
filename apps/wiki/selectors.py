"""Published wiki content: what readers see in lists."""

from collections import defaultdict

from django.db.models import prefetch_related_objects

from apps.core.versioning import current_versions

from .models import Faq, Page


# Guides merged into another one before go-live: their old pages are left out of every list and
# search, and their links go to the guide that replaced them (views_read.page). No retire step needed.
MERGED_GUIDES = {
    "building-or-changing-a-report-used-in-controls": "can-you-trust-the-report",
}


def current_pages():
    """(page, version) pairs for published, non-retired pages, sorted by title."""
    versions = [v for v in current_versions(Page) if v.entity.slug not in MERGED_GUIDES]
    prefetch_related_objects(versions, "platform")  # lists show the platform name
    pairs = [(version.entity, version) for version in versions]
    return sorted(pairs, key=lambda pair: pair[1].title.lower())


def pages_by_pk():
    return {page.pk: (page, version) for page, version in current_pages()}


def related_current(faq_version, current):
    """(page, version) pairs for the FAQ's related pages that are published; `current` is pages_by_pk()."""
    return [current[page.pk] for page in faq_version.related_pages.all() if page.pk in current]


def faq_groups():
    """Published questions grouped by topic, with questions that apply everywhere (topic None) first.

    Returns [(topic or None, [(faq, version, [related (page, version)])])].
    """
    pages = pages_by_pk()
    versions = sorted(current_versions(Faq), key=lambda v: v.entity_id)
    prefetch_related_objects(versions, "topic", "related_pages")
    by_topic = defaultdict(list)
    for version in versions:
        by_topic[version.topic].append((version.entity, version, related_current(version, pages)))
    topics = sorted((t for t in by_topic if t is not None), key=lambda t: (t.position, t.name))
    return [(t, by_topic[t]) for t in ([None] if None in by_topic else []) + topics]
