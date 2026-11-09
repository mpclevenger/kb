"""Helpers for the wiki view tests."""

from datetime import date

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext

from apps.core import versioning as v
from apps.wiki.models import Faq, FaqVersion, Page, PageVersion, unique_page_slug


def make_page(proposer, approver, publish_it=True, **over):
    fields = dict(
        title="GitHub Actions runners",
        section="best_practice",
        body="<h2>Purpose</h2><p>Why.</p><h3>Detail</h3><p>More.</p>",
        owner_role="Tech Risk",
        review_by=date(2099, 1, 1),
    )
    fields.update(over)
    entity, version = v.create_entity(
        Page, PageVersion, proposer, {"slug": unique_page_slug(fields["title"])}, **fields
    )
    if publish_it:
        v.submit(version, proposer)
        v.approve_and_publish(version, approver)
    return entity


def make_faq(proposer, approver, publish_it=True, related=(), **over):
    fields = dict(question="Who approves exceptions?", answer="Tech Risk does.\n\nAsk early.")
    fields.update(over)
    entity, version = v.create_entity(Faq, FaqVersion, proposer, {}, **fields)
    version.related_pages.set(related)
    if publish_it:
        v.submit(version, proposer)
        v.approve_and_publish(version, approver)
    return entity


def page_post(**over):
    data = {
        "title": "GitHub Actions runners",
        "section": "best_practice",
        "platform": "",
        "body": "",
        "owner_role": "Tech Risk",
        "review_by": "2027-11-01",
        "references": "[]",
    }
    data.update(over)
    return data


def assert_in_html(needle, haystack):
    """Like `needle in haystack`, but ignores attribute order, quotes and spacing in the HTML."""
    SimpleTestCase().assertInHTML(needle, haystack)


def count_queries(client, url, **extra):
    """How many database queries one GET of `url` makes (after a warm-up request)."""
    client.get(url, **extra)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url, **extra)
    assert response.status_code == 200
    return len(queries)
