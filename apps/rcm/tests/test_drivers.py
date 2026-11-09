"""Risk drivers (RD ids from the risk engine): model, links, pages, the explorer column and filter, and Tech Risk-only access."""

import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import NoReverseMatch, reverse

from apps.core import versioning as v
from apps.core.tests.support import As, publish, published_control, published_driver, risk_post
from apps.rcm import selectors, services
from apps.rcm.models import Risk, RiskDriverLink

EXPLORER_LINK = re.compile(r'href="/rcm/(\?[^"]*)?"')

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("sso")]


def published_risk(topic, owner, reviewer, drivers=(), controls=(), **content):
    fields = dict(title="Leavers keep access", statement="Access is not removed.", owner_role="IAM")
    fields.update(content)
    entity, version = services.create_risk(owner.user, topic, **fields)
    services.set_risk_links(version, owner.user, controls=controls, drivers=drivers)
    return entity, publish(version, reviewer.user)


# Model and services

def test_drivers_take_the_engine_id_and_the_site_has_no_driver_form(owner, reviewer):
    first, _ = published_driver(owner.user, reviewer.user, ident="RD16")
    assert first.ident == "RD16"
    assert first.get_absolute_url() == reverse("rcm:driver", args=["RD16"])
    assert first.get_list_url() == reverse("rcm:explorer")
    for name in ("driver_new", "driver_edit"):
        with pytest.raises(NoReverseMatch):
            reverse(f"rcm:{name}", args=["RD16"] if name == "driver_edit" else [])


@pytest.mark.parametrize(
    "references,message",
    [
        ([{"label": "Guide", "url": "ftp://example.com"}], "must start with https:// or http://"),
        ([{"label": "", "url": "https://example.com"}], "add a label"),
        ("not a list", "Use a list of references"),
    ],
)
def test_driver_references_are_validated(owner, references, message):
    _, version = services.create_driver(owner.user, "RD90", title="D", description="d", owner_role="o")
    version.references = references
    with pytest.raises(ValidationError, match=message):
        version.full_clean(exclude=["entity", "number", "proposed_by"])


def test_risk_driver_links_are_unique_per_pair(owner, access, live_driver):
    _, version = services.create_risk(owner.user, access, title="R", statement="s", owner_role="o")
    services.set_risk_links(version, owner.user, drivers=[live_driver])
    with pytest.raises(IntegrityError), transaction.atomic():
        RiskDriverLink.objects.create(risk_version=version, driver=live_driver)


def test_new_risk_draft_copies_driver_links_and_submitted_links_lock(owner, reviewer, access, live_driver):
    risk, version = published_risk(access, owner, reviewer, drivers=[live_driver])
    draft = v.propose_change(risk, owner.user, "Reword", title="Sharper")
    assert [l.driver for l in draft.driver_links.all()] == [live_driver]
    assert version.driver_links.count() == 1

    v.submit(draft, owner.user)
    with pytest.raises(v.ImmutableVersionError):
        RiskDriverLink.objects.create(risk_version=draft, driver=live_driver)
    with pytest.raises(v.ImmutableVersionError):
        draft.driver_links.get().delete()


def test_set_risk_links_replaces_drivers(owner, access, live_driver):
    _, version = services.create_risk(owner.user, access, title="R", statement="s", owner_role="o")
    services.set_risk_links(version, owner.user, drivers=[live_driver])
    services.set_risk_links(version, owner.user)
    assert version.driver_links.count() == 0


# Selectors

def test_matrix_rows_list_published_non_retired_drivers(owner, reviewer, access, live_driver):
    retired, _ = published_driver(owner.user, reviewer.user, title="Retired one")
    unpublished = services.create_driver(owner.user, "RD91", title="Draft", description="d", owner_role="o")[0]
    published_risk(access, owner, reviewer, drivers=[live_driver, retired, unpublished])
    publish(v.propose_retirement(retired, owner.user, "Gone"), reviewer.user)
    (row,) = selectors.risk_control_matrix()
    assert [d["driver"] for d in row.drivers] == [live_driver]
    assert row.drivers[0]["version"].title == "Legacy systems without central sign-in"


def test_risks_for_driver_carry_coverage(owner, reviewer, access, live_driver, live_control):
    covered, _ = published_risk(
        access, owner, reviewer, drivers=[live_driver], controls=[(live_control, "full", "Reviews all")]
    )
    gap, _ = published_risk(access, owner, reviewer, drivers=[live_driver], title="Gap")
    published_risk(access, owner, reviewer, title="Unrelated")
    rows = selectors.risks_for_driver(live_driver, selectors.risk_control_matrix())
    assert {r.risk.ident: r.coverage for r in rows} == {covered.ident: "covered", gap.ident: "unmapped"}


# Risk form

def test_risk_form_lists_only_published_drivers_and_round_trips(owner, reviewer, access, live_driver):
    services.create_driver(owner.user, "RD92", title="Draft only", description="d", owner_role="o")
    html = owner.get(reverse("rcm:risk_new")).content.decode()
    assert f"{live_driver.ident} Legacy systems without central sign-in" in html
    assert "Draft only" not in html

    owner.post(reverse("rcm:risk_new"), risk_post(access, drivers=[live_driver.pk]))
    risk = Risk.objects.get()
    assert [l.driver for l in risk.versions.get().driver_links.all()] == [live_driver]

    publish(risk.versions.get(), reviewer.user)
    url = reverse("rcm:risk_edit", args=[risk.ident])
    assert owner.get(url).context["form"]["drivers"].value() == [live_driver.pk]
    owner.post(url, risk_post(access, drivers=[live_driver.pk], change_summary="Reworded"))
    assert [l.driver for l in risk.versions.get(number=2).driver_links.all()] == [live_driver]
    owner.post(url, risk_post(access, change_summary="Reworded"))
    assert risk.versions.get(number=2).driver_links.count() == 0


def test_risk_form_rejects_unknown_driver(owner, access):
    draft = services.create_driver(owner.user, "RD92", title="Draft only", description="d", owner_role="o")[0]
    response = owner.post(reverse("rcm:risk_new"), risk_post(access, drivers=[draft.pk]))
    assert response.status_code == 200 and "drivers" in response.context["form"].errors
    assert not Risk.objects.exists()


# Driver page

def test_driver_page_shows_content_and_risks_with_coverage(owner, reviewer, access, live_driver, live_control):
    published_risk(access, owner, reviewer, drivers=[live_driver], controls=[(live_control, "full", "Reviews all")])
    published_risk(access, owner, reviewer, drivers=[live_driver], title="Gap risk")
    html = owner.get(live_driver.get_absolute_url()).content.decode()
    assert "RD01" in html and "Legacy systems without central sign-in" in html
    assert "Some systems keep their own user accounts." in html
    assert "Head of Infrastructure" in html
    assert "TRAC risks" in html and "Leavers keep access" in html and "Gap risk" in html
    assert "Covered" in html and "Unmapped" in html
    assert "Propose a change" not in html


def test_driver_page_shows_indicators_category_and_references(owner, reviewer):
    entity, _ = published_driver(
        owner.user, reviewer.user, category="Technology",
        indicators=[{"type": "leading", "text": "Systems with their own user lists."}, {"type": "lagging", "text": "Late leavers."}],
        references=[{"label": "Guide", "url": "https://example.com/g"}],
    )
    html = owner.get(entity.get_absolute_url()).content.decode()
    assert "Systems with their own user lists." in html and "Technology" in html
    assert "Leading" in html and "Lagging" in html and "Late leavers." in html
    assert 'href="https://example.com/g"' in html


@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_readers_view_driver_pages_without_edit_links(live_driver, group):
    response = As("reader", group).get(live_driver.get_absolute_url())
    html = response.content.decode()
    assert response.status_code == 200 and "Propose a change" not in html
    assert not EXPLORER_LINK.search(html)


def test_unpublished_driver_is_hidden_from_readers(owner):
    entity, _ = services.create_driver(owner.user, "RD90", title="D", description="d", owner_role="o")
    assert As("reader", "ro").get(entity.get_absolute_url()).status_code == 404
    assert owner.get(entity.get_absolute_url() + "?version=1").status_code == 200


def test_risk_page_lists_its_drivers(owner, reviewer, access, live_driver):
    risk, _ = published_risk(access, owner, reviewer, drivers=[live_driver])
    html = As("reader", "ro").get(risk.get_absolute_url()).content.decode()
    assert "What raises it" in html and live_driver.get_absolute_url() in html
    bare, _ = published_risk(access, owner, reviewer, title="No drivers")
    assert "What raises it" not in owner.get(bare.get_absolute_url()).content.decode()


# Explorer

def test_explorer_has_drivers_column_filter_and_button(owner, reviewer, access, live_driver):
    other, _ = published_driver(owner.user, reviewer.user, title="High staff and contractor turnover")
    with_both, _ = published_risk(access, owner, reviewer, drivers=[live_driver, other], title="Both")
    published_risk(access, owner, reviewer, drivers=[other], title="One")
    published_risk(access, owner, reviewer, title="Plain")
    response = owner.get(reverse("rcm:explorer"))
    html = response.content.decode()
    assert "<th scope=\"col\">Drivers</th>" in html
    assert f'data-kind="driver" href="{live_driver.get_absolute_url()}"' in html
    assert "RD01" in html and "High staff and contractor turnover" in html and ">Driver<" in html
    assert 'name="driver"' in html and "Any driver" in html
    assert "RD02 High staff and contractor turnover</option>" in html
    assert "New driver" not in html

    filtered = owner.get(reverse("rcm:explorer"), {"driver": live_driver.ident}).content.decode()
    assert f'<option value="{live_driver.ident}" selected>' in filtered
    assert re.findall(r'class="col-id" href="[^"]*/(R-[A-Z]+-\d+)/', filtered) == [with_both.ident]


def test_explorer_ignores_unknown_driver_and_keeps_it_in_tab_links(owner, reviewer, access, live_driver):
    published_risk(access, owner, reviewer, drivers=[live_driver])
    published_risk(access, owner, reviewer, title="Plain")
    html = owner.get(reverse("rcm:explorer"), {"driver": "RD99"}).content.decode()
    assert "Plain" in html and "&driver=RD99" not in html
    tabs = owner.get(reverse("rcm:explorer"), {"driver": live_driver.ident}).content.decode()
    assert f"&driver={live_driver.ident}" in tabs


# Tech Risk only

@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_explorer_is_403_for_everyone_but_tech_risk(live_control, group):
    outsider = As("outsider", group)
    assert outsider.get(reverse("rcm:explorer")).status_code == 403
    assert outsider.get(reverse("rcm:explorer"), {"view": "controls"}, HTTP_HX_REQUEST="true").status_code == 403


def test_explorer_is_200_for_tech_risk_including_partials(owner, live_control):
    assert owner.get(reverse("rcm:explorer")).status_code == 200
    assert owner.get(reverse("rcm:explorer"), {"key": "1"}, HTTP_HX_REQUEST="true").status_code == 200


def nav_labels(response):
    nav = response.content.decode().split('aria-label="Primary"')[1].split("</nav>")[0]
    return re.findall(r'<a href="[^"]*"[^>]*>([^<]+)</a>', nav)


@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_nav_hides_risks_and_controls_and_review_queue_from_non_tech_risk(live_control, group):
    labels = nav_labels(As("reader", group).get(live_control.get_absolute_url()))
    assert "Library" in labels
    assert "Risks and controls" not in labels and "Review queue" not in labels


def test_nav_shows_risks_and_controls_to_tech_risk(owner, live_control):
    assert "Risks and controls" in nav_labels(owner.get(live_control.get_absolute_url()))


def test_home_link_to_explorer_is_tech_risk_only(owner, live_control):
    link = f'<a href="{reverse("rcm:explorer")}">Risks and controls</a>'
    assert link in owner.get(reverse("core:home")).content.decode()
    assert link not in As("reader", "ro").get(reverse("core:home")).content.decode()


@pytest.mark.parametrize("group", ["co", "ro", "aud"])
def test_item_pages_for_readers_link_to_the_topic_page_not_the_explorer(owner, reviewer, access, group):
    stage = access.stages.first()
    control, _ = published_control(access, owner.user, reviewer.user, stage=stage)
    risk, _ = published_risk(access, owner, reviewer, stage=stage)
    topic_url = reverse("topics:detail", args=[access.slug])
    for entity in (control, risk):
        html = As("reader", group).get(entity.get_absolute_url()).content.decode()
        assert not EXPLORER_LINK.search(html)
        assert f'href="{topic_url}"' in html and f'href="{topic_url}?stage={stage.pk}"' in html
