"""The risk engine's files: read, check, and bring into the site.

The risk engine is the master list of risk drivers (RD01, RD02 ...) and of its own risks.
TRAC keeps copies of two engine files that you refresh by copying them over:

    content/engine/driver_mapping.yaml   the drivers
    content/engine/risks/*.yaml          the engine's risks, one file per risk category

TRAC adds its own details for each driver in one file, content/drivers/drivers.json.

`read_engine` checks all three and returns plain-word problems and warnings. `sync` then
- makes a TRAC driver (with versions, approvals and history like other content) for every engine driver,
- replaces the read-only copy of the engine's risks (the engine owns them, so they have no drafts),
- adds an empty drivers.json entry for any engine driver that has none yet.
Whether a driver already matches the files is decided by `apps.core.content_sync`.
Scoring rules are kept as text. They are never run.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from apps.core import content_sync as cs
from apps.core import versioning as v

from . import services
from .models import (
    NO_OWNER_YET, Driver, DriverKind, DriverVersion, EngineRisk, EngineRiskDriver, Risk,
)

ENGINE_DIR = Path(settings.BASE_DIR) / "content" / "engine"
DRIVERS_FILE = Path(settings.BASE_DIR) / "content" / "drivers" / "drivers.json"

DRIVER_ID = re.compile(r"^RD\d{2}$")
DRIVER_TOKEN = re.compile(r"\bRD\d+\b")

MAPPING_KEYS = {"trigger", "questionnaire_fields", "rationale"}
RISK_KEYS = {
    "domain", "category", "name", "description", "example", "likelihood_scoring", "likelihood_drivers",
    "impact_drivers", "impact_scoring", "framework_mappings",
}
EMPTY_ENTRY = {"title": "", "category": "", "owner_role": "", "indicators": [], "trac_risks": []}


@dataclass
class Report:
    drivers: dict = field(default_factory=dict)  # "RD01" -> {"trigger", "questionnaire_fields", "rationale"}
    risks: list = field(default_factory=list)
    file_entries: dict = field(default_factory=dict)  # what drivers.json holds now
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def missing_entries(self):
        """Engine drivers that drivers.json has no entry for yet."""
        return sorted(self.drivers.keys() - self.file_entries.keys())

    def extras(self, driver_id):
        """TRAC's own details for a driver: its drivers.json entry, or an empty one."""
        return self.file_entries.get(driver_id) or EMPTY_ENTRY


def read_engine(engine_dir=None, drivers_file=None):
    engine_dir = Path(engine_dir or ENGINE_DIR)
    report = Report()
    _read_mapping(engine_dir / "driver_mapping.yaml", report)
    _read_risk_files(engine_dir / "risks", report)
    _read_drivers_file(Path(drivers_file or DRIVERS_FILE), report)
    return report


def _load_yaml(path, report):
    """The file's contents, or None after adding a plain-word problem."""
    if not path.exists():
        report.problems.append(f"{path.name}: the file is missing. Copy it from the risk engine into {path.parent}.")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = f" near line {mark.line + 1}" if mark else ""
        report.problems.append(f"{path.name}: the file isn't valid YAML{line}. Check the indentation and colons.")
        return None


def _is_list_of_text(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


# driver_mapping.yaml

def _read_mapping(path, report):
    data = _load_yaml(path, report)
    if data is None:
        return
    if not isinstance(data, dict) or not isinstance(data.get("risk_drivers"), dict):
        report.problems.append(f"{path.name}: expected a 'risk_drivers' section that lists RD01, RD02 and so on.")
        return
    for key in data.keys() - {"risk_drivers"}:
        report.warnings.append(f"{path.name}: '{key}' isn't a known section; ignored.")
    for raw_id, entry in data["risk_drivers"].items():
        driver_id, where = str(raw_id), f"{path.name}, {raw_id}"
        if not DRIVER_ID.match(driver_id):
            report.problems.append(f"{where}: the id must look like RD01 (RD and two digits, no hyphen).")
        elif not isinstance(entry, dict):
            report.problems.append(f"{where}: expected trigger, questionnaire_fields and rationale.")
        else:
            _read_mapping_entry(driver_id, entry, where, report)


def _read_mapping_entry(driver_id, entry, where, report):
    for key in entry.keys() - MAPPING_KEYS:
        report.warnings.append(f"{where}: '{key}' isn't a known field; ignored.")
    trigger, fields, rationale = entry.get("trigger") or "", entry.get("questionnaire_fields") or [], entry.get("rationale") or ""
    for name, value in (("trigger", trigger), ("rationale", rationale)):
        if not isinstance(value, str):
            report.problems.append(f"{where}, field '{name}': expected text.")
    if not _is_list_of_text(fields):
        report.problems.append(f"{where}, field 'questionnaire_fields': expected a list of ids such as [RD01].")
    report.drivers[driver_id] = {
        "trigger": trigger.strip() if isinstance(trigger, str) else "",
        "questionnaire_fields": fields if _is_list_of_text(fields) else [],
        "rationale": rationale.strip() if isinstance(rationale, str) else "",
    }


# content/engine/risks/*.yaml

def _key_name(key):
    """Tolerate 'framework mappings' and 'framework-mappings' for framework_mappings."""
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def _read_risk_files(folder, report):
    files = sorted(folder.glob("*.yaml"))
    if not files:
        report.problems.append(f"No risk files (.yaml) found in {folder}. Copy the engine's risk files there.")
    seen = {}
    for path in files:
        data = _load_yaml(path, report)
        if data is None:
            continue
        items = data["risks"] if isinstance(data, dict) and "risks" in data else data
        for number, item in enumerate(items if isinstance(items, list) else [items], start=1):
            risk = _read_risk(path, number, item, report)
            if risk is None:
                continue
            if risk["key"] in seen:
                report.problems.append(
                    f"{path.name}, risk '{risk['name']}': the same domain, category and name is already in {seen[risk['key']]}."
                )
                continue
            seen[risk["key"]] = path.name
            report.risks.append(risk)
    if report.drivers:
        for risk in report.risks:
            _check_driver_ids(risk, report)


def _read_risk(path, number, item, report):
    if not isinstance(item, dict):
        report.problems.append(f"{path.name}, risk number {number}: expected domain, category, name and so on.")
        return None
    item = {_key_name(key): value for key, value in item.items()}
    name = item.get("name")
    where = f"{path.name}, risk '{name}'" if isinstance(name, str) and name.strip() else f"{path.name}, risk number {number}"
    for key in item.keys() - RISK_KEYS:
        report.warnings.append(f"{where}: '{key}' isn't a known field; ignored.")
    problems_before = len(report.problems)
    for key in ("domain", "category", "name"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            report.problems.append(f"{where}: field '{key}' is missing.")
    risk = {
        "domain": str(item.get("domain") or "").strip(), "category": str(item.get("category") or "").strip(),
        "name": str(item.get("name") or "").strip(), "source_file": path.name,
        "description": str(item.get("description") or "").strip(), "example": str(item.get("example") or "").strip(),
        "likelihood_scoring": _levels(item.get("likelihood_scoring"), "likelihood_scoring", where, report),
        "impact_scoring": _impact_scoring(item.get("impact_scoring"), where, report),
        "framework_mappings": json.loads(json.dumps(item.get("framework_mappings") or {}, default=str)),
    }
    for kind in DriverKind.values:
        ids = item.get(f"{kind}_drivers") or []
        if not _is_list_of_text(ids):
            report.problems.append(f"{where}, field '{kind}_drivers': expected a list such as [RD01, RD02].")
            ids = []
        risk[f"{kind}_drivers"] = ids
    if len(report.problems) > problems_before:
        return None
    risk["key"] = slugify(f"{risk['domain']} {risk['category']} {risk['name']}")
    return risk


def _levels(value, name, where, report):
    """Level name -> rule text (or null). Kept as text."""
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(rule, (str, type(None))) for rule in value.values()):
        report.problems.append(f"{where}, field '{name}': expected levels such as critical and high, each with rule text.")
        return {}
    return {str(level): rule for level, rule in value.items()}


def _impact_scoring(value, where, report):
    if value is None:
        return {}
    if not isinstance(value, dict):
        report.problems.append(f"{where}, field 'impact_scoring': expected impact types such as financial_impact.")
        return {}
    return {str(kind): _levels(levels, f"impact_scoring, {kind}", where, report) for kind, levels in value.items()}


def _check_driver_ids(risk, report):
    """Every RD id named in the driver lists or inside a scoring rule must be in driver_mapping.yaml."""
    named = {}
    for kind in DriverKind.values:
        for driver_id in risk[f"{kind}_drivers"]:
            named.setdefault(driver_id, f"{kind}_drivers")
    rules = [("likelihood_scoring", rule) for rule in risk["likelihood_scoring"].values()]
    for kind, levels in risk["impact_scoring"].items():
        rules += [(f"impact_scoring, {kind}", rule) for rule in levels.values()]
    for place, rule in rules:
        for driver_id in DRIVER_TOKEN.findall(rule or ""):
            named.setdefault(driver_id, place)
    for driver_id, place in named.items():
        if driver_id not in report.drivers:
            report.problems.append(
                f"{risk['source_file']}, risk '{risk['name']}': {driver_id} (in {place}) isn't in driver_mapping.yaml."
            )


# content/drivers/drivers.json

def _read_drivers_file(path, report):
    if not path.exists():
        return  # sync_engine creates it
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.problems.append(f"{path.name}: the file isn't valid JSON (line {error.lineno}). Check commas, quotes and brackets.")
        return
    if not isinstance(data, dict):
        report.problems.append(f"{path.name}: expected one entry per driver, such as \"RD01\": {{ ... }}.")
        return
    for driver_id, entry in data.items():
        where = f"{path.name}, {driver_id}"
        if not DRIVER_ID.match(driver_id):
            report.problems.append(f"{where}: the id must look like RD01.")
        elif _entry_has_shape(entry, where, report):
            report.file_entries[driver_id] = entry
            if report.drivers and driver_id not in report.drivers:
                report.warnings.append(f"{where}: not in driver_mapping.yaml, so it is kept but not used.")
    for driver_id, driver in report.drivers.items():
        _check_driver_fields(driver_id, driver, report, path.name)


def _entry_has_shape(entry, where, report):
    if not isinstance(entry, dict):
        report.problems.append(f"{where}: expected title, category, owner_role, indicators and trac_risks.")
        return False
    before = len(report.problems)
    for key in EMPTY_ENTRY.keys() - entry.keys():
        report.problems.append(f"{where}: '{key}' is missing (use \"\" or [] when there is nothing to say).")
    for key in entry.keys() - EMPTY_ENTRY.keys():
        report.problems.append(f"{where}: '{key}' isn't a known field.")
    for key in ("title", "category", "owner_role"):
        if key in entry and not isinstance(entry[key], str):
            report.problems.append(f"{where}, field '{key}': expected text.")
    return len(report.problems) == before


def _check_driver_fields(driver_id, driver, report, file_name):
    """Run the model's own checks (lengths, indicator types) on what the site would store."""
    extra = report.extras(driver_id)
    try:
        DriverVersion(**driver_fields(driver_id, driver, extra)).full_clean(exclude=["entity", "number", "proposed_by"])
    except ValidationError as error:
        for name, messages in error.message_dict.items():
            report.problems.append(f"{file_name}, {driver_id}, field '{name}': {' '.join(messages)}")


def driver_fields(driver_id, engine, extra):
    """The DriverVersion fields for one driver: engine text plus TRAC's own details."""
    return {
        "title": extra["title"].strip() or driver_id,
        "description": engine["rationale"],
        "trigger": engine["trigger"],
        "questionnaire_fields": list(engine["questionnaire_fields"]),
        "category": extra["category"].strip(),
        "owner_role": extra["owner_role"].strip() or NO_OWNER_YET,
        "indicators": extra["indicators"],
        "trac_risks": extra["trac_risks"],
    }


def unknown_trac_risks(report):
    """Warnings for drivers.json risk ids that no TRAC risk has (yet)."""
    known = set(Risk.objects.values_list("ident", flat=True))
    return [
        f"drivers.json, {driver_id}: TRAC risk {ident} doesn't exist in the site."
        for driver_id in sorted(report.drivers)
        for ident in report.extras(driver_id)["trac_risks"]
        if ident not in known
    ]


def add_missing_entries(report, path=None):
    """Write an empty drivers.json entry for each engine driver without one. Nothing is ever removed."""
    path = Path(path or DRIVERS_FILE)
    entries = {**report.file_entries, **{driver_id: dict(EMPTY_ENTRY) for driver_id in report.missing_entries}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(entries.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report.file_entries = entries


# sync

def sync(report, user, say, publish=False, force=False, dry_run=False, drivers_file=None):
    """Bring the site in line with the engine files. Returns the driver outcomes (a list of cs.Outcome)."""
    cs.ensure_can_publish(publish)
    outcomes = []
    with transaction.atomic():
        missing = report.missing_entries
        if missing:
            if not dry_run:
                add_missing_entries(report, drivers_file)
            say(f"{'Would add' if dry_run else 'Added'} empty drivers.json entries for: {', '.join(missing)}.")
        for driver_id in sorted(report.drivers):
            outcome = _sync_driver(driver_id, report, user, publish, force, dry_run)
            outcomes.append(outcome)
            say(outcome.message)
        _mention_drivers_gone_from_engine(report, say)
        if dry_run:
            say(f"Would replace the engine risks with the {len(report.risks)} in the engine files.")
        else:
            _replace_engine_risks(report)
            say(f"Engine risks: {len(report.risks)} loaded (the previous copy was replaced).")
    return outcomes


def _sync_driver(driver_id, report, user, publish, force, dry_run):
    fields = driver_fields(driver_id, report.drivers[driver_id], report.extras(driver_id))
    digest = cs.entry_hash(fields)
    entity = Driver.objects.filter(ident=driver_id).first()
    published = entity.current() if entity else None
    matches = bool(
        published and published.kind != v.Kind.RETIRE and all(getattr(published, k) == val for k, val in fields.items())
    )
    decision = cs.decide(entity, driver_id, digest, force=force, site_matches_file=matches, export_command=None)
    if decision.kind == cs.IS_NEW:
        if dry_run:
            return cs.Outcome(cs.NEW, f"{driver_id}: would be created as a draft.")
        entity, version = services.create_driver(user, driver_id, **fields)
        cs.record(entity, version, digest)
        cs.finish(version, user, publish)
        return cs.Outcome(cs.NEW, f"{driver_id}: created as a {'published driver' if publish else 'draft'}.")
    if decision.kind != cs.UPDATE:
        if decision.remember and not dry_run:
            cs.record(entity, published, digest)
        return cs.Outcome(decision.outcome, decision.message)
    if dry_run:
        return cs.Outcome(cs.UPDATED, f"{driver_id}: would be updated from the engine files.")
    version = v.propose_change(entity, user, "Updated from the risk engine files", **fields)
    cs.record(entity, version, digest)
    cs.finish(version, user, publish)
    return cs.Outcome(cs.UPDATED, f"{driver_id}: {'published an update' if publish else 'drafted an update'}.")


def _mention_drivers_gone_from_engine(report, say):
    for driver in Driver.objects.exclude(ident__in=report.drivers):
        current = driver.current()
        if current and current.kind != v.Kind.RETIRE:
            say(f"{driver.ident}: no longer in driver_mapping.yaml. It was left as it is; retire it in the site if it is gone for good.")


def _replace_engine_risks(report):
    EngineRisk.objects.all().delete()
    drivers = {d.ident: d for d in Driver.objects.filter(ident__in=report.drivers)}
    risk_fields = ("key", "domain", "category", "name", "description", "example", "likelihood_scoring",
                   "impact_scoring", "framework_mappings", "source_file")
    created = EngineRisk.objects.bulk_create(EngineRisk(**{k: risk[k] for k in risk_fields}) for risk in report.risks)
    EngineRiskDriver.objects.bulk_create(
        EngineRiskDriver(engine_risk=row, driver=drivers[driver_id], kind=kind)
        for row, risk in zip(created, report.risks)
        for kind in DriverKind.values
        for driver_id in dict.fromkeys(risk[f"{kind}_drivers"])
    )
