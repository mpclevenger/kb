"""The risk engine files: reading and checking, the sync into drivers and engine risks, drivers.json, and the pages."""

import io
import json
import shutil
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import versioning as v
from apps.core.tests.support import As, make_user, publish
from apps.rcm import engine_files, services
from apps.rcm.models import Driver, DriverVersion, EngineRisk, EngineRiskDriver, NO_OWNER_YET

pytestmark = pytest.mark.django_db

SHIPPED = Path(engine_files.ENGINE_DIR)
SHIPPED_DRIVERS = Path(engine_files.DRIVERS_FILE)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """A private copy of the shipped sample files, so a test can change them freely."""
    folder = tmp_path / "engine"
    shutil.copytree(SHIPPED, folder)
    drivers = tmp_path / "drivers" / "drivers.json"
    drivers.parent.mkdir()
    shutil.copy(SHIPPED_DRIVERS, drivers)
    monkeypatch.setattr(engine_files, "ENGINE_DIR", folder)
    monkeypatch.setattr(engine_files, "DRIVERS_FILE", drivers)
    return folder


@pytest.fixture
def lead():
    return make_user("lead", "tech_risk")


def sync(**options):
    out = io.StringIO()
    call_command("sync_engine", user="lead", stdout=out, stderr=io.StringIO(), **options)
    return out.getvalue()


def change_mapping(engine, driver_id, **fields):
    path = engine / "driver_mapping.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["risk_drivers"][driver_id].update(fields)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def read(engine):
    return engine_files.read_engine(engine, engine_files.DRIVERS_FILE)


def write_risk(engine, name, text):
    (engine / "risks" / name).write_text(text, encoding="utf-8")


def problems_of(engine):
    return "\n".join(read(engine).problems)


# Reading the files

def test_the_shipped_sample_files_are_valid():
    report = engine_files.read_engine()
    assert report.problems == [] and report.warnings == [] and report.missing_entries == []
    assert sorted(report.drivers) == ["RD01", "RD02", "RD03", "RD16", "RD36", "RD39", "RD50", "RD54"]
    assert {r["name"] for r in report.risks} == {
        "External data breach based on tool use", "Production change causes an outage or wrong results",
    }
    assert report.drivers["RD36"]["questionnaire_fields"] == ["RD36", "RD37"]
    assert report.drivers["RD01"]["trigger"] == "(get(RD01)==TRUE)"


def test_the_samples_say_they_are_samples():
    for path in (SHIPPED / "driver_mapping.yaml", *sorted((SHIPPED / "risks").glob("*.yaml"))):
        assert path.read_text(encoding="utf-8").startswith("# SAMPLE")


def test_keys_are_read_tolerantly_and_mappings_kept_as_they_are(engine):
    cyber = {r["name"]: r for r in read(engine).risks}["External data breach based on tool use"]
    change = {r["name"]: r for r in read(engine).risks}["Production change causes an outage or wrong results"]
    assert cyber["key"] == "cyber-unauthorized-access-external-data-breach-based-on-tool-use"
    # the change file spells "framework mappings" with a space and "sub_caractersitics"
    assert change["framework_mappings"] == {"iso_25010": [{"characteristic": "Reliability", "sub_caractersitics": "Maturity"}]}
    assert cyber["likelihood_scoring"]["critical"].startswith(">.80 and (RD01 in ad")
    assert cyber["impact_scoring"]["financial_impact"]["critical"] is None


def test_a_file_can_hold_a_list_of_risks_and_unknown_keys_only_warn(engine):
    write_risk(engine, "two.yaml", """
risks:
  - {domain: Ops, category: People, name: One, likelihood_drivers: [RD01], surprise: 1}
  - {domain: Ops, category: People, name: Two, impact_drivers: [RD02]}
""")
    report = read(engine)
    assert report.problems == []
    assert {"One", "Two"} <= {r["name"] for r in report.risks}
    assert any("two.yaml" in w and "'surprise' isn't a known field" in w for w in report.warnings)


def test_unknown_driver_ids_are_named_with_the_file_and_the_risk(engine):
    write_risk(engine, "bad.yaml", """
domain: Ops
category: People
name: Lost badge
likelihood_drivers: [RD01, RD99]
likelihood_scoring: {high: "RD01 in ad and RD77 in ad"}
impact_scoring:
  financial_impact: {low: "RD88 in ad"}
""")
    text = problems_of(engine)
    for driver_id, place in (("RD99", "likelihood_drivers"), ("RD77", "likelihood_scoring"), ("RD88", "impact_scoring, financial_impact")):
        assert f"bad.yaml, risk 'Lost badge': {driver_id} (in {place}) isn't in driver_mapping.yaml." in text


def test_a_risk_without_a_name_and_a_duplicate_are_reported(engine):
    write_risk(engine, "nameless.yaml", "domain: Ops\ncategory: People\n")
    write_risk(engine, "again.yaml", (engine / "risks" / "cyber-unauthorized-access.yaml").read_text(encoding="utf-8"))
    text = problems_of(engine)
    assert "nameless.yaml, risk number 1: field 'name' is missing." in text
    assert "cyber-unauthorized-access.yaml, risk 'External data breach based on tool use': the same domain, category and name is already in again.yaml." in text


@pytest.mark.parametrize("fileName, content, fragment", [
    ("driver_mapping.yaml", "risk_drivers: [unclosed\n", "driver_mapping.yaml: the file isn't valid YAML"),
    ("driver_mapping.yaml", "something: else\n", "expected a 'risk_drivers' section"),
    ("driver_mapping.yaml", "risk_drivers:\n  RD-01: {rationale: x}\n", "driver_mapping.yaml, RD-01: the id must look like RD01"),
    ("driver_mapping.yaml", "risk_drivers:\n  RD01: {questionnaire_fields: nope}\n", "field 'questionnaire_fields'"),
])
def test_mapping_mistakes_are_explained(engine, fileName, content, fragment):
    (engine / fileName).write_text(content, encoding="utf-8")
    assert fragment in problems_of(engine)


def test_unknown_top_level_mapping_keys_only_warn(engine):
    path = engine / "driver_mapping.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "version: 3\n", encoding="utf-8")
    report = read(engine)
    assert report.problems == [] and "driver_mapping.yaml: 'version' isn't a known section; ignored." in report.warnings


def test_missing_engine_files_are_reported(tmp_path):
    report = engine_files.read_engine(tmp_path, tmp_path / "none.json")
    assert any("driver_mapping.yaml: the file is missing" in p for p in report.problems)
    assert any("No risk files" in p for p in report.problems)


# drivers.json

def edit_drivers(mutate):
    data = json.loads(engine_files.DRIVERS_FILE.read_text(encoding="utf-8"))
    mutate(data)
    engine_files.DRIVERS_FILE.write_text(json.dumps(data), encoding="utf-8")


def test_a_bad_indicator_type_names_the_file_and_the_driver(engine):
    edit_drivers(lambda d: d["RD01"].update(indicators=[{"type": "sideways", "text": "x"}]))
    assert "drivers.json, RD01, field 'indicators': Each indicator needs a type of leading or lagging" in problems_of(engine)


@pytest.mark.parametrize("mutate, fragment", [
    (lambda d: d["RD01"].pop("owner_role"), "drivers.json, RD01: 'owner_role' is missing"),
    (lambda d: d["RD01"].update(extra=1), "drivers.json, RD01: 'extra' isn't a known field"),
    (lambda d: d["RD01"].update(title=5), "drivers.json, RD01, field 'title': expected text"),
    (lambda d: d["RD01"].update(trac_risks="R-AC-01"), "field 'trac_risks'"),
    (lambda d: d.update({"D-01": {}}), "drivers.json, D-01: the id must look like RD01"),
])
def test_drivers_json_mistakes_are_explained(engine, mutate, fragment):
    edit_drivers(mutate)
    assert fragment in problems_of(engine)


def test_drivers_json_that_is_not_json_is_explained(engine):
    engine_files.DRIVERS_FILE.write_text('{"RD01": ', encoding="utf-8")
    assert "drivers.json: the file isn't valid JSON (line 1)" in problems_of(engine)


def test_an_entry_for_a_driver_not_in_the_engine_only_warns(engine):
    edit_drivers(lambda d: d.update(RD99=dict(engine_files.EMPTY_ENTRY)))
    report = read(engine)
    assert report.problems == [] and any("RD99: not in driver_mapping.yaml" in w for w in report.warnings)


def test_a_missing_drivers_json_is_created_with_an_empty_entry_for_every_engine_driver(engine, lead):
    engine_files.DRIVERS_FILE.unlink()
    sync()
    data = json.loads(engine_files.DRIVERS_FILE.read_text(encoding="utf-8"))
    assert list(data) == sorted(read(engine).drivers) and len(data) == 8
    assert all(entry == engine_files.EMPTY_ENTRY for entry in data.values())
    assert DriverVersion.objects.get(entity__ident="RD01").owner_role == NO_OWNER_YET


def test_new_engine_drivers_are_added_to_drivers_json_and_nothing_is_ever_removed(engine, lead):
    edit_drivers(lambda d: d.update(RD99={**engine_files.EMPTY_ENTRY, "title": "Kept"}))
    edit_drivers(lambda d: d.pop("RD54"))
    out = sync()
    data = json.loads(engine_files.DRIVERS_FILE.read_text(encoding="utf-8"))
    assert data["RD54"] == engine_files.EMPTY_ENTRY and data["RD99"]["title"] == "Kept" and data["RD01"]["title"]
    assert "Added empty drivers.json entries for: RD54." in out


# The sync

def test_new_drivers_become_drafts_with_engine_and_trac_fields(engine, lead):
    out = sync()
    assert "Done: drivers 8 new, 0 updated, 0 unchanged, 0 skipped." in out
    rd01 = Driver.objects.get(ident="RD01").versions.get()
    assert rd01.status == v.Status.DRAFT and rd01.proposed_by == lead
    assert rd01.title == "Systems with their own user accounts" and rd01.category == "Technology"
    assert rd01.description.startswith("The application keeps its own user accounts")
    assert rd01.trigger == "(get(RD01)==TRUE)" and rd01.questionnaire_fields == ["RD01"]
    assert rd01.indicators[0] == {"type": "leading", "text": "Number of systems that keep their own user lists."}
    assert rd01.trac_risks == ["R-AC-03"]
    rd50 = Driver.objects.get(ident="RD50").versions.get()
    assert rd50.title == "Feeds the financial statements" and rd50.owner_role == NO_OWNER_YET
    assert sorted(Driver.objects.values_list("ident", flat=True))[:2] == ["RD01", "RD02"]


def test_an_empty_title_shows_the_rd_id(engine, lead):
    edit_drivers(lambda d: d["RD02"].update(title=""))
    sync()
    assert Driver.objects.get(ident="RD02").versions.get().title == "RD02"


def test_the_second_sync_says_unchanged_and_replaces_the_engine_risks_only(engine, lead):
    sync()
    first = set(EngineRisk.objects.values_list("pk", flat=True))
    out = sync()
    assert "Done: drivers 0 new, 0 updated, 8 unchanged, 0 skipped." in out
    assert Driver.objects.get(ident="RD01").versions.count() == 1
    assert set(EngineRisk.objects.values_list("pk", flat=True)).isdisjoint(first)  # a fresh copy each time


def test_engine_risks_are_a_read_only_copy_with_their_driver_links(engine, lead):
    sync()
    risk = EngineRisk.objects.get(name="External data breach based on tool use")
    assert (risk.domain, risk.category, risk.source_file) == ("Cyber", "Unauthorized access", "cyber-unauthorized-access.yaml")
    assert risk.description.startswith("Someone outside the firm")
    links = {(l.driver.ident, l.kind) for l in risk.driver_links.all()}
    assert links == {("RD01", "likelihood"), ("RD36", "likelihood"), ("RD54", "likelihood"), ("RD02", "impact"), ("RD54", "impact")}
    assert risk.likelihood_scoring["high"] == ">.60 and (RD01 in ad or RD03 in ad)"


def test_the_engine_risks_follow_the_files_when_a_risk_goes_away(engine, lead):
    sync()
    (engine / "risks" / "technology-change-failure.yaml").unlink()
    out = sync()
    assert EngineRisk.objects.count() == 1 and "Engine risks: 1 loaded" in out
    assert not EngineRiskDriver.objects.filter(engine_risk__name__startswith="Production").exists()


def test_a_changed_driver_is_proposed_after_the_first_draft_is_finished(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    sync(publish=True)
    change_mapping(engine, "RD01", rationale="New wording from the engine.")
    out = sync()
    assert "RD01: drafted an update." in out and "7 unchanged" in out
    driver = Driver.objects.get(ident="RD01")
    assert driver.open_proposal().number == 2 and driver.current().number == 1
    assert driver.open_proposal().description == "New wording from the engine."


def test_a_change_already_in_progress_is_skipped(engine, lead):
    sync()
    change_mapping(engine, "RD01", rationale="New wording.")
    out = sync()
    assert "RD01: a change is already in progress in the site; finish or discard it first." in out
    assert "1 skipped" in out and Driver.objects.get(ident="RD01").versions.count() == 1


def test_a_driver_edited_in_the_site_is_skipped_unless_forced(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    sync(publish=True)
    driver = Driver.objects.get(ident="RD01")
    edit = v.propose_change(driver, lead, "Edited in the site", owner_role="Someone else")
    v.submit(edit, lead)
    v.approve_and_publish(edit, lead)
    change_mapping(engine, "RD01", rationale="New wording.")
    out = sync()
    assert "RD01: edited in the site since the file was last synced. Use --force to replace that edit with the file." in out
    assert "export" not in out and driver.current().owner_role == "Someone else"

    out = sync(force=True)
    assert "RD01: drafted an update." in out
    assert driver.open_proposal().owner_role == "Head of Infrastructure"


def test_publish_makes_the_drivers_official_in_single_approver_mode(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    out = sync(publish=True)
    assert "RD01: created as a published driver." in out
    assert not DriverVersion.objects.exclude(status="published").exists()


def test_publish_is_refused_without_single_approver_mode_and_changes_nothing(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = False
    with pytest.raises(CommandError, match="single-approver mode"):
        sync(publish=True)
    assert not Driver.objects.exists() and not EngineRisk.objects.exists()


def test_dry_run_says_what_would_happen_and_changes_nothing(engine, lead):
    engine_files.DRIVERS_FILE.unlink()
    out = sync(dry_run=True)
    assert "RD01: would be created as a draft." in out and "Would add empty drivers.json entries" in out
    assert "Would replace the engine risks with the 2" in out and "Would change: drivers 8 new" in out
    assert not Driver.objects.exists() and not EngineRisk.objects.exists() and not engine_files.DRIVERS_FILE.exists()


def test_problems_stop_the_sync_before_anything_changes(engine, lead):
    write_risk(engine, "bad.yaml", "domain: Ops\ncategory: People\nname: X\nimpact_drivers: [RD99]\n")
    with pytest.raises(CommandError, match="(?s)Nothing was changed.*bad.yaml, risk 'X': RD99"):
        sync()
    assert not Driver.objects.exists()


def test_a_driver_that_left_the_engine_is_left_alone_with_a_note(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    sync(publish=True)
    path = engine / "driver_mapping.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["risk_drivers"]["RD39"]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    for risk_file in (engine / "risks").glob("*.yaml"):  # no risk may still name it
        risk_file.write_text(risk_file.read_text(encoding="utf-8").replace("RD39", "RD36"), encoding="utf-8")
    out = sync()
    assert "RD39: no longer in driver_mapping.yaml. It was left as it is" in out
    assert Driver.objects.get(ident="RD39").current() is not None


def test_check_engine_reports_unknown_trac_risks_as_warnings(engine, capsys):
    edit_drivers(lambda d: d["RD02"].update(trac_risks=["R-AC-77"]))
    out = io.StringIO()
    call_command("check_engine", stdout=out)
    assert "Warning: drivers.json, RD02: TRAC risk R-AC-77 doesn't exist in the site." in out.getvalue()
    assert "All good: 8 drivers, 2 engine risks." in out.getvalue()


def test_check_engine_exits_with_the_problems(engine, capsys):
    write_risk(engine, "bad.yaml", "domain: Ops\ncategory: People\nname: X\nimpact_drivers: [RD99]\n")
    out = io.StringIO()
    with pytest.raises(SystemExit):
        call_command("check_engine", stdout=out)
    assert "Problem: bad.yaml, risk 'X': RD99" in out.getvalue() and "1 problem(s) found" in out.getvalue()


# Pages

@pytest.fixture
def loaded(engine, lead, settings):
    settings.ALLOW_SELF_APPROVAL = True
    sync(publish=True)


@pytest.mark.usefixtures("sso")
def test_the_engine_risks_page_is_for_tech_risk_only(loaded):
    url = reverse("rcm:engine_risks")
    assert As("tr1", "tr").get(url).status_code == 200
    for group in ("co", "aud", "ro"):
        assert As(f"user-{group}", group).get(url).status_code == 403
    from django.test import Client
    assert Client().get(url).status_code == 403


@pytest.mark.usefixtures("sso")
def test_the_engine_risks_page_groups_risks_and_links_drivers(loaded):
    html = As("tr1", "tr").get(reverse("rcm:engine_risks")).content.decode()
    assert html.index("Cyber") < html.index("Unauthorized access") < html.index("External data breach based on tool use")
    assert html.index("Cyber") < html.index("Technology") < html.index("Change failure")
    assert "Someone outside the firm gets hold of confidential data" in html and "A support tool that can read every client record" in html
    assert 'href="/rcm/drivers/RD01/"' in html and 'title="Systems with their own user accounts"' in html
    assert "Likelihood drivers:" in html and "Impact drivers:" in html
    assert 'id="cyber-unauthorized-access-external-data-breach-based-on-tool-use"' in html


@pytest.mark.usefixtures("sso")
def test_scoring_rules_are_shown_as_text_in_a_collapsed_block_and_never_run(loaded):
    EngineRisk.objects.filter(name__startswith="External").update(
        likelihood_scoring={"low": "dc >= 0", "critical": "__import__('os').system('x') and <b>bold</b>"})
    html = As("tr1", "tr").get(reverse("rcm:engine_risks")).content.decode()
    assert '<details class="topic-faq">' in html and "<details class=\"topic-faq\" open" not in html
    assert "<code>__import__(&#x27;os&#x27;).system(&#x27;x&#x27;) and &lt;b&gt;bold&lt;/b&gt;</code>" in html
    assert html.index(">Critical<") < html.index(">Low<")  # the usual order, whatever order the file used
    assert "<caption>Financial impact</caption>" in html and "No rule" in html


@pytest.mark.usefixtures("sso")
def test_framework_mappings_are_never_shown(loaded):
    html = As("tr1", "tr").get(reverse("rcm:engine_risks")).content.decode()
    for text in ("Confidentiality", "exfiltration", "iso_25010", "Maturity", "nist_sp"):
        assert text not in html


@pytest.mark.usefixtures("sso")
def test_the_explorer_links_to_the_engine_risks(loaded):
    html = As("tr1", "tr").get(reverse("rcm:explorer")).content.decode()
    assert f'href="{reverse("rcm:engine_risks")}"' in html and "Engine risks" in html


@pytest.mark.usefixtures("sso")
def test_the_driver_page_shows_engine_details_indicators_and_links(loaded, access, lead):
    risk, version = services.create_risk(lead, access, title="Leavers keep access", statement="s", owner_role="IAM")
    assert risk.ident == "R-AC-01"
    publish(version, As("approver", "tr").user)
    edit_drivers(lambda d: d["RD01"].update(trac_risks=["R-AC-01"]))
    call_command("sync_engine", user="lead", force=True, stdout=io.StringIO())
    driver = Driver.objects.get(ident="RD01")
    publish(driver.open_proposal(), As("approver", "tr").user)

    html = As("tr1", "tr").get(driver.get_absolute_url()).content.decode()
    assert "RD01" in html and "Systems with their own user accounts" in html
    assert "The application keeps its own user accounts" in html
    assert "From the risk engine" in html and "(get(RD01)==TRUE)" in html and "Questionnaire fields" in html
    assert "Leading" in html and "Lagging" in html and "Late leavers" not in html and "Leavers whose access was removed late." in html
    assert "Engine risks this driver feeds" in html and "External data breach based on tool use" in html
    assert "likelihood" in html.lower()
    assert "TRAC risks" in html and "Leavers keep access" in html and risk.get_absolute_url() in html
    assert "Propose a change" not in html


@pytest.mark.usefixtures("sso")
def test_a_risk_named_in_drivers_json_shows_the_driver_on_the_risk_page_and_the_explorer(loaded, access, lead):
    risk, version = services.create_risk(lead, access, title="Leavers keep access", statement="s", owner_role="IAM")
    publish(version, As("approver", "tr").user)
    edit_drivers(lambda d: d["RD16"].update(trac_risks=[risk.ident]))
    call_command("sync_engine", user="lead", force=True, stdout=io.StringIO())
    publish(Driver.objects.get(ident="RD16").open_proposal(), As("approver", "tr").user)
    page = As("reader", "ro").get(risk.get_absolute_url()).content.decode()
    assert "What raises it" in page and "/rcm/drivers/RD16/" in page
    explorer = As("tr1", "tr").get(reverse("rcm:explorer")).content.decode()
    assert "/rcm/drivers/RD16/" in explorer


@pytest.mark.usefixtures("sso")
def test_readers_see_the_trac_wording_but_not_the_engine_details(loaded):
    html = As("reader", "ro").get(Driver.objects.get(ident="RD01").get_absolute_url()).content.decode()
    assert "The application keeps its own user accounts" in html
    assert "From the risk engine" not in html and "get(RD01)" not in html and "Engine risks this driver feeds" not in html


@pytest.mark.usefixtures("sso")
def test_a_driver_without_an_owner_shows_not_assigned_yet(loaded):
    html = As("tr1", "tr").get(Driver.objects.get(ident="RD50").get_absolute_url()).content.decode()
    assert NO_OWNER_YET in html


@pytest.mark.usefixtures("sso")
def test_query_counts_do_not_grow_with_the_number_of_engine_risks(loaded):
    owner = As("tr1", "tr")
    urls = [reverse("rcm:engine_risks"), Driver.objects.get(ident="RD54").get_absolute_url()]

    def counts():
        result = []
        for url in urls:
            owner.get(url)
            with CaptureQueriesContext(connection) as queries:
                assert owner.get(url).status_code == 200
            result.append(len(queries))
        return result

    def add_risks(first, count):
        driver = Driver.objects.get(ident="RD54")
        for n in range(first, first + count):
            risk = EngineRisk.objects.create(
                key=f"extra-{n}", domain=f"Domain {n % 3}", category=f"Category {n}", name=f"Risk {n}",
                likelihood_scoring={"high": "RD54 in ad"}, impact_scoring={"financial_impact": {"low": "dc >= 1"}})
            EngineRiskDriver.objects.create(engine_risk=risk, driver=driver, kind="likelihood")
            EngineRiskDriver.objects.create(engine_risk=risk, driver=driver, kind="impact")

    add_risks(0, 3)
    small = counts()
    add_risks(3, 12)
    assert counts() == small


@pytest.mark.usefixtures("sso")
def test_the_engine_risk_list_links_drivers_that_are_still_drafts(engine, lead):
    sync()  # nothing published yet
    html = As("tr1", "tr").get(reverse("rcm:engine_risks")).content.decode()
    assert 'href="/rcm/drivers/RD01/"' in html
    assert As("tr1", "tr").get("/rcm/drivers/RD01/?version=1").status_code == 200
