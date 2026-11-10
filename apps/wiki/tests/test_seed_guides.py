"""Checks the starter guides load as drafts and say what they should."""

import re

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.accounts.roles import READ_ONLY
from apps.core import versioning as v
from apps.core.tests.support import As, make_user
from apps.wiki.models import Page, PageVersion
from apps.wiki.starter_guides import GUIDES_DIR, load_guides

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

INDEX = "wiki:index"

AUDIT_TITLES = ["Working with auditors: what trips teams up", "Before your control review: be ready to answer"]
EXCEPTIONS = "When an exception is appropriate"
EVIDENCE = "Automating control evidence with a well-controlled repository"
GHES_TITLES = ["GitHub Actions runners", "Repository management"]
DOCUMENTATION = "What every system should have documented"
LIFECYCLE = "Initiative lifecycle"
ROLE_PHRASES = ("head of tech risk", "tech risk helps describe the risk")
TIMELINES = "Recommended timelines by BCP tier"
OVERSIGHT = "Oversight levels"
TITLES = [EXCEPTIONS, EVIDENCE, DOCUMENTATION, LIFECYCLE, TIMELINES, OVERSIGHT, *AUDIT_TITLES, *GHES_TITLES]
HELP_LINE = "If you're unsure, Tech Risk can help."
BANNED = ("reach out", "tell tech risk", "agree it with tech risk", "route", "through tech risk", "agreed channel", "standard")


# seed_guides

@pytest.fixture
def seeded(owner, topics):
    call_command("seed_platforms")
    call_command("seed_guides", user=owner.username)
    return PageVersion.objects.filter(title__in=TITLES)


def test_seed_creates_unpublished_guides_in_the_right_sections(seeded, owner):
    assert sorted(seeded.values_list("title", flat=True)) == sorted(TITLES)
    for version in seeded:
        assert version.status == v.Status.DRAFT and version.proposed_by == owner.user
        assert version.owner_role == "Tech Risk" and version.review_by > version.proposed_at.date()
    assert seeded.get(title=EXCEPTIONS).section == "build"
    assert seeded.get(title=EVIDENCE).section == "build"
    for title in GHES_TITLES:
        version = seeded.get(title=title)
        assert version.section == "best_practice" and version.platform.name == "GitHub Enterprise Server"
    assert {v_.section for v_ in seeded.filter(title__in=AUDIT_TITLES)} == {"audit_prep"}
    assert seeded.get(title=EXCEPTIONS).platform is None
    assert all(page.current() is None for page in Page.objects.all())


def test_seeded_content_has_no_pointing_back_to_tech_risk(seeded):
    # Oversight levels describes Tech Risk's own part in the process, and "Standard" is the name of a
    # level shared with the initiative tracker, so it is checked separately below.
    for version in seeded.exclude(title=OVERSIGHT):
        text = re.sub(r"<[^>]+>", " ", version.body).lower()
        for phrase in BANNED:
            assert phrase not in text, (version.title, phrase)
        # These phrases describe Tech Risk's role; they don't send readers to Tech Risk.
        pointers = text
        for role_phrase in ROLE_PHRASES:
            pointers = pointers.replace(role_phrase, "")
        assert pointers.count("tech risk") == 1 and text.count(HELP_LINE.lower()) == 1


def test_seed_is_idempotent(seeded, owner):
    call_command("seed_guides", user=owner.username)
    assert PageVersion.objects.count() == len(load_guides())


def test_seed_names_the_file_when_a_guide_file_is_broken(owner, tmp_path):
    (tmp_path / "broken.md").write_text("No header here.\n", encoding="utf-8")
    with pytest.raises(CommandError, match="broken.md"):
        call_command("seed_guides", user=owner.username, folder=str(tmp_path))
    assert not PageVersion.objects.exists()


def test_seed_warns_and_loads_untagged_for_an_unknown_platform(owner, tmp_path, capsys):
    (tmp_path / "tagged.md").write_text(
        f"---\ntitle: Tagged guide\nsection: build\nplatform: Nonexistent Platform\n---\nText.\n\n{HELP_LINE}\n", encoding="utf-8")
    call_command("seed_guides", user=owner.username, folder=str(tmp_path))
    assert "no platform named 'Nonexistent Platform'" in capsys.readouterr().out
    assert PageVersion.objects.get(title="Tagged guide").platform is None


def test_seed_refuses_users_who_cannot_propose():
    make_user("plain", READ_ONLY)
    with pytest.raises(CommandError, match="Tech Risk"):
        call_command("seed_guides", user="plain")
    with pytest.raises(CommandError, match="No user"):
        call_command("seed_guides", user="nobody")
    assert not PageVersion.objects.exists()


def test_seeded_auditors_guide_has_the_sections_as_guidance_not_tables(seeded):
    body = seeded.get(title=AUDIT_TITLES[0]).body
    for heading in ("Evidence", "Populations and reports", "Running the control", "When things change", "Walkthroughs and requests"):
        assert f"<h2>{heading}</h2>" in body
    assert "<table" not in body and "Watch out for" not in body
    assert "recurring findings" not in body.lower()
    assert "Control work is done with named accounts" in body
    assert "and the reason before the control runs." in body
    assert "with what changed and when, because both versions may be tested." in body


def test_seeded_review_guide_covers_before_during_and_after(seeded):
    body = seeded.get(title=AUDIT_TITLES[1]).body
    for heading in ("The questions you will be asked", "What helps to have ready", "During the review", "After the review"):
        assert f"<h2>{heading}</h2>" in body
    for question in ("The risk.", "The design.", "Who.", "Completeness.", "Evidence.", "Reports.", "Changes."):
        assert f"<strong>{question}</strong>" in body


def test_seeded_exceptions_guide_covers_the_agreed_sections(seeded):
    body = seeded.get(title=EXCEPTIONS).body
    for heading in ("Exception criteria", "Compensating controls", "Risk treatment"):
        assert f"<h2>{heading}</h2>" in body
    assert "<h3>Who accepts it</h3>" in body
    assert body.rstrip().endswith(f"<p>{HELP_LINE}</p>")


def test_seeded_drafts_publish_and_show_under_their_sections(seeded, owner, reviewer):
    for version in seeded:
        v.submit(version, owner.user)
        v.approve_and_publish(version, reviewer.user)
    reader = As("reader", "ro")
    audit = reader.get(reverse(INDEX), {"section": "audit_prep"}).content.decode()
    assert all(title in audit for title in AUDIT_TITLES) and EXCEPTIONS not in audit
    assert EXCEPTIONS in reader.get(reverse(INDEX), {"section": "build"}).content.decode()


def test_documentation_guide_lists_all_nine_documents_as_minimum(seeded):
    body = seeded.get(title=DOCUMENTATION).body
    minimum = body.split("Recommended additions")[0]
    for name in ("System overview", "Architecture diagram", "Data flow diagram", "Access model", "Runbooks",
                 "Change and release process", "Jobs and interfaces list", "Logging and alerting summary",
                 "Contacts and escalation"):
        assert name in minimum
    assert seeded.get(title=DOCUMENTATION).section == "best_practice"


def test_documentation_guide_asks_for_technical_connection_details(seeded):
    minimum = seeded.get(title=DOCUMENTATION).body.split("Recommended additions")[0].lower()
    for detail in ("connection type", "protocol and port", "authenticates", "tls", "mfa"):
        assert detail in minimum


# Initiative lifecycle: the initiative tracker links to each stage heading, so these anchors must not change.
LIFECYCLE_ANCHORS = [
    "stage-0-intake", "stage-1-mobilize-and-design", "stage-2-build-and-configure", "stage-3-test-and-validate",
    "stage-4-cutover-and-go-live", "stage-5-hypercare-and-stabilize", "stage-6-close",
]


def test_initiative_lifecycle_has_a_stable_link_for_every_stage(seeded, owner, reviewer):
    version = seeded.get(title=LIFECYCLE)
    assert version.section == "build" and version.entity.slug == "initiative-lifecycle"
    v.submit(version, owner.user)
    v.approve_and_publish(version, reviewer.user)
    html = As("reader", "ro").get("/guides/initiative-lifecycle/").content.decode()
    for anchor in LIFECYCLE_ANCHORS:
        assert f'id="{anchor}"' in html, anchor
    for heading in ("Controls to consider", "Evidence to keep"):
        assert html.count(f"<th>{heading}</th>") == 7
    assert html.count("<strong>The auditor will ask:</strong>") == 7


def test_timelines_compare_tier_0_and_1_with_every_other_tier(seeded):
    version = seeded.get(title=TIMELINES)
    assert version.section == "best_practice"
    for heading in ("Fixing vulnerabilities", "Logging and alerting", "Backups and recovery", "Access"):
        assert f"<h2>{heading}</h2>" in version.body
    assert version.body.count("<th>Tier 0 and tier 1</th><th>All other tiers</th>") == 4


def lifecycle_items():
    """{stage number: item count}, counted from the Initiative lifecycle file's headings."""
    items, stage = {}, None
    for line in (GUIDES_DIR / "initiative-lifecycle.md").read_text(encoding="utf-8").splitlines():
        if match := re.match(r"## Stage (\d+)\b", line):
            stage = int(match.group(1))
            items[stage] = []
        elif match := re.match(r"#### Item (\d+)\b", line):
            items[stage].append(int(match.group(1)))
    return items


def test_every_checklist_item_has_a_stable_link(seeded, owner, reviewer):
    items = lifecycle_items()
    assert sorted(items) == [0, 1, 2, 3, 4, 5, 6]
    version = seeded.get(title=LIFECYCLE)
    v.submit(version, owner.user)
    v.approve_and_publish(version, reviewer.user)
    html = As("reader", "ro").get("/guides/initiative-lifecycle/").content.decode()
    for stage, numbers in items.items():
        assert numbers == list(range(1, len(numbers) + 1)), f"Stage {stage} items must be numbered 1, 2, 3 in order"
        for n in numbers:
            assert f'id="stage-{stage}-item-{n}"' in html, (stage, n)
    assert sum(len(numbers) for numbers in items.values()) == 30
    assert 'href="/guides/oversight-levels/"' in html


def test_oversight_levels_page(seeded, owner, reviewer):
    version = seeded.get(title=OVERSIGHT)
    assert version.section == "build" and version.entity.slug == "oversight-levels"
    text = re.sub(r"<[^>]+>", " ", version.body).lower()
    for phrase in set(BANNED) - {"standard"}:
        assert phrase not in text, phrase
    assert text.count(HELP_LINE.lower()) == 1
    assert "<th>Stage exit</th><th>Enhanced</th><th>Standard</th><th>Light</th>" in version.body
    assert version.body.count("<tr>") == 7  # header and six stage exits
    assert 'href="/guides/initiative-lifecycle/"' in version.body
