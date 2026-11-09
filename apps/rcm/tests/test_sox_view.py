"""The SOX page: controls at the first (most important) level, grouped by topic, filtered by category."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As, anonymous, publish, published_control
from apps.rcm import services

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

URL = "/rcm/sox/"


def sox_control(topic, owner, reviewer, **content):
    content.setdefault("level", "key")
    return published_control(topic, owner.user, reviewer.user, **content)[0]


def test_url_name():
    assert reverse("rcm:sox") == URL


def test_lists_only_first_level_published_controls(access, owner, reviewer):
    sox_control(access, owner, reviewer, title="Needed for SOX")
    sox_control(access, owner, reviewer, title="Only non-key", level="non-key")
    sox_control(access, owner, reviewer, title="Only supporting", level="supporting")
    entity, version = services.create_control(
        owner.user, access, title="Still a draft", why="w", owner_role="o", nature="detective",
        method="manual", frequency="monthly", level="key",
    )
    html = owner.get(URL).content.decode()
    assert "Needed for SOX" in html
    assert "Only non-key" not in html and "Only supporting" not in html
    assert "Still a draft" not in html


def test_retired_control_is_left_out(access, owner, reviewer):
    control = sox_control(access, owner, reviewer, title="Soon retired")
    retire = v.propose_retirement(control, owner.user, "No longer needed")
    publish(retire, reviewer.user)
    assert "Soon retired" not in owner.get(URL).content.decode()


def test_groups_follow_topic_order(topics, owner, reviewer):
    first, last = list(topics.filter(is_active=True))[0], list(topics.filter(is_active=True))[-1]
    sox_control(last, owner, reviewer, title="In the last topic")
    sox_control(first, owner, reviewer, title="In the first topic")
    groups = owner.get(URL).context["groups"]
    assert [g["topic"] for g in groups] == [first, last]


def test_category_filter(access, owner, reviewer):
    sox_control(access, owner, reviewer, title="Database one", categories=["database"])
    sox_control(access, owner, reviewer, title="Identity one", categories=["identity"])
    html = owner.get(URL, {"category": "database"}).content.decode()
    assert "Database one" in html and "Identity one" not in html


def test_bad_category_is_ignored(access, owner, reviewer):
    sox_control(access, owner, reviewer, title="Database one", categories=["database"])
    response = owner.get(URL, {"category": "nonsense"})
    assert response.context["category"] == ""
    assert "Database one" in response.content.decode()


def test_empty_state_when_nothing_matches(access, owner, reviewer):
    sox_control(access, owner, reviewer, categories=["database"])
    assert "No key controls to show" in owner.get(URL, {"category": "network"}).content.decode()


def test_sox_only_count(access, owner, reviewer):
    sox_control(
        access, owner, reviewer, title="Has SOX lines",
        criteria=[{"name": "A", "items": ["plain", {"text": "x", "sox_only": True}, {"text": "y", "sox_only": True}]}],
    )
    assert "Checks for SOX apps: 2" in owner.get(URL).content.decode()


def test_no_note_without_sox_only_lines(access, owner, reviewer):
    sox_control(access, owner, reviewer)
    assert "Checks for SOX apps" not in owner.get(URL).content.decode()


@pytest.mark.parametrize("group", ["ro", "co", "aud"])
def test_readable_by_every_role(access, owner, reviewer, group):
    sox_control(access, owner, reviewer)
    assert As(f"user-{group}", group).get(URL).status_code == 200


def test_anonymous_is_refused():
    assert anonymous().get(URL).status_code == 403


def test_links_in_both_directions(access, owner, reviewer):
    control = sox_control(access, owner, reviewer, title="Linked")
    page = owner.get(URL).content.decode()
    assert reverse("rcm:control", args=[control.ident]) in page
    assert URL in owner.get(reverse("rcm:control", args=[control.ident])).content.decode()
    assert URL in owner.get("/").content.decode()


def test_control_page_below_first_level_has_no_link(access, owner, reviewer):
    control = sox_control(access, owner, reviewer, level="non-key")
    assert URL not in owner.get(reverse("rcm:control", args=[control.ident])).content.decode()


def test_query_count_does_not_grow(access, owner, reviewer):
    def count():
        owner.get(URL)
        with CaptureQueriesContext(connection) as queries:
            owner.get(URL)
        return len(queries)

    for n in range(3):
        sox_control(access, owner, reviewer, title=f"Small {n}", categories=["database"])
    small = count()
    for n in range(10):
        sox_control(access, owner, reviewer, title=f"Large {n}", categories=["database"])
    assert count() == small


def test_first_level_comes_from_levels_file(access, owner, reviewer, tmp_path, monkeypatch):
    """Putting another level first in levels.yaml changes which controls the SOX page lists."""
    from apps.rcm import levels

    file = tmp_path / "levels.yaml"
    file.write_text(
        "levels:\n  - {key: supporting, label: Supporting, open: true}\n  - {key: key, label: Key, open: false}\n"
    )
    monkeypatch.setattr(levels, "LEVELS_FILE", file)
    levels.clear_cache()
    try:
        sox_control(access, owner, reviewer, title="Is a key one", level="key")
        sox_control(access, owner, reviewer, title="Is a supporting one", level="supporting")
        html = owner.get(URL).content.decode()
        assert "Is a supporting one" in html and "Is a key one" not in html
    finally:
        levels.clear_cache()


def test_title_and_wording(access, owner, reviewer):
    sox_control(access, owner, reviewer)
    html = owner.get(URL).content.decode()
    assert "Key controls for SOX in-scope apps" in html
    assert "formal SOX risk and control matrix" in html
    assert "Required for SOX" not in html
