"""References on controls, risks and wiki pages; owner roles on risks."""

import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core import versioning as v
from apps.rcm import services
from apps.rcm.models import Control, ControlVersion, RiskVersion
from apps.core.tests.support import control_post, publish, published_control, risk_post
from apps.wiki.models import PageVersion

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]

GOOD = [{"label": "Access management standard", "url": "https://example.com/standard"}]


def refs(*rows):
    return json.dumps([{"label": label, "url": url} for label, url in rows])


# Model validation

@pytest.fixture
def control_version(owner, access):
    return services.create_control(
        owner.user, access, title="C", why="w", owner_role="o", nature="detective", method="manual", frequency="daily",
    )[1]


@pytest.fixture
def risk_version(owner, access):
    return services.create_risk(owner.user, access, title="R", statement="s", owner_role="o")[1]


@pytest.fixture
def page_version(access):
    return PageVersion(
        title="P", section="build", owner_role="o", review_by="2030-01-01",
        entity=None,
    )


@pytest.mark.parametrize("kind", ["control_version", "risk_version"])
@pytest.mark.parametrize(
    "bad, message",
    [
        ([{"label": "Standard", "url": "ftp://example.com"}], "must start with https:// or http://"),
        ([{"label": "Standard", "url": "example.com"}], "must start with https:// or http://"),
        ([{"label": " ", "url": "https://example.com"}], "add a label"),
        ([{"url": "https://example.com"}], "add a label"),
        ([{"label": f"L{n}", "url": "https://example.com"} for n in range(11)], "at most 10"),
        ("https://example.com", "Use a list"),
    ],
)
def test_bad_references_are_rejected(kind, bad, message, request):
    version = request.getfixturevalue(kind)
    version.references = bad
    with pytest.raises(ValidationError) as error:
        version.full_clean()
    assert message in error.value.message_dict["references"][0]


@pytest.mark.parametrize("kind", ["control_version", "risk_version"])
def test_ten_references_and_http_links_are_fine(kind, request):
    version = request.getfixturevalue(kind)
    version.references = [{"label": f"L{n}", "url": "http://example.com"} for n in range(10)]
    version.full_clean()


def test_wiki_page_references_are_validated(page_version):
    page_version.references = [{"label": "", "url": "https://example.com"}]
    with pytest.raises(ValidationError) as error:
        page_version.clean()
    assert "add a label" in error.value.message_dict["references"][0]
    page_version.references = GOOD
    page_version.clean()


# Forms

def test_control_references_round_trip_and_blank_rows_are_dropped(owner, access):
    rows = refs(("Access management standard", "https://example.com/standard"), ("", ""))
    assert owner.post(reverse("rcm:control_new"), control_post(access, references=rows)).status_code == 302
    version = ControlVersion.objects.get()
    assert version.references == GOOD
    html = owner.get(reverse("rcm:control_edit", args=[version.entity.ident])).content.decode()
    assert "Access management standard" in html and "Add a reference" in html


def test_risk_references_round_trip(owner, access):
    data = risk_post(access, references=refs(("NIST", "https://example.com/nist")))
    assert owner.post(reverse("rcm:risk_new"), data).status_code == 302
    assert RiskVersion.objects.get().references == [{"label": "NIST", "url": "https://example.com/nist"}]


@pytest.mark.parametrize("row, message", [
    (("Standard", "javascript:alert(1)"), "must start with https:// or http://"),
    (("", "https://example.com"), "add a label"),
])
def test_form_shows_reference_errors(owner, access, row, message):
    response = owner.post(reverse("rcm:control_new"), control_post(access, references=refs(row)))
    assert response.status_code == 200
    assert message in response.content.decode()
    assert not Control.objects.exists()


def test_form_rejects_more_than_ten(owner, access):
    rows = refs(*[(f"L{n}", "https://example.com") for n in range(11)])
    response = owner.post(reverse("rcm:risk_new"), risk_post(access, references=rows))
    assert response.status_code == 200 and "at most 10" in response.content.decode()


def test_risk_owner_role_round_trips(owner, access):
    owner.post(reverse("rcm:risk_new"), risk_post(access, owner_role="Application owner"))
    assert RiskVersion.objects.get().owner_role == "Application owner"
    html = owner.get(reverse("rcm:risk_new")).content.decode()
    assert "Owner role" in html and "The role accountable for this" in html


# Detail pages

def test_control_page_lists_references_above_the_footer(owner, reviewer, access):
    control, _ = published_control(
        access, owner.user, reviewer.user,
        references=[{"label": "CIS benchmark", "url": "https://example.com/cis"}],
    )
    html = owner.get(control.get_absolute_url()).content.decode()
    assert '<a href="https://example.com/cis" target="_blank" rel="noopener noreferrer">CIS benchmark</a>' in html
    assert html.index("References") < html.index('aria-label="Governance"')


def test_risk_page_lists_references(owner, reviewer, access):
    _, version = services.create_risk(
        owner.user, access, title="R", statement="s", owner_role="o", references=GOOD
    )
    publish(version, reviewer.user)
    html = owner.get(version.entity.get_absolute_url()).content.decode()
    assert 'href="https://example.com/standard"' in html and "Access management standard" in html


def test_references_hidden_when_empty(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user)
    assert "References" not in owner.get(control.get_absolute_url()).content.decode()


# New drafts

def test_references_are_copied_to_new_drafts(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user, references=GOOD)
    assert v.propose_change(control, owner.user, "Reword", title="New").references == GOOD
    _, version = services.create_risk(owner.user, access, title="R", statement="s", owner_role="o", references=GOOD)
    publish(version, reviewer.user)
    assert v.propose_change(version.entity, owner.user, "Reword", title="New").references == GOOD
