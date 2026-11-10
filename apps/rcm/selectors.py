"""Read-side queries over published, non-retired register items."""

from dataclasses import dataclass, field

from django.db.models import Prefetch, prefetch_related_objects

from apps.core.versioning import current_versions

from . import levels
from .models import Control, Coverage, Driver, DriverKind, EngineRisk, EngineRiskDriver, Risk


def _current(model):
    """(entity, live version) pairs ordered by ID, from one query."""
    pairs = [(version.entity, version) for version in current_versions(model)]
    return sorted(pairs, key=lambda pair: pair[0].ident)


def current_controls():
    return _current(Control)


def current_risks():
    return _current(Risk)


def current_drivers():
    return _current(Driver)


def sox_only_count(groups):
    """How many criteria lines in these groups are flagged SOX only."""
    return sum(
        1
        for group in groups
        for item in group.get("items", [])
        if isinstance(item, dict) and item.get("sox_only")
    )


def top_level_controls(category=None):
    """Current controls at the most important level, optionally only those tagged with `category` (a Category key)."""
    top = levels.first_key()
    return [
        (control, version)
        for control, version in current_controls()
        if version.level == top and (not category or category in (version.categories or []))
    ]


def sort_by_level(items, level_of):
    """The items with the most important level first. Items at the same level keep their order."""
    return sorted(items, key=lambda item: levels.position(level_of(item)))


@dataclass
class LevelGroup:
    """Folded items that share one level, listed under that level's label."""

    key: str
    label: str
    items: list = field(default_factory=list)


def fold_by_level(items, level_of):
    """Split a list of controls for readers into (shown, more).

    This is the one rule behind "important controls first, the rest under More controls" on every
    reader page. `level_of(item)` gives an item's level key. `shown` holds the items whose level is
    open in levels.yaml, most important first. `more` is a list of LevelGroup for the folded levels.
    If nothing is at an open level, nothing is folded: the items are shown as they are, since a
    "More controls" fold with nothing above it would hide the only controls there are.
    """
    ranked = sort_by_level(items, level_of)
    shown = [item for item in ranked if levels.is_open(level_of(item))]
    if not shown:
        return ranked, []
    more = []
    for item in ranked:
        key = level_of(item)
        if levels.is_open(key):
            continue
        if not more or more[-1].key != key:
            more.append(LevelGroup(key=key, label=levels.label(key)))
        more[-1].items.append(item)
    return shown, more


def fold_pairs(pairs):
    """fold_by_level for (control, version) pairs."""
    return fold_by_level(pairs, lambda pair: pair[1].level)


def drivers_naming_risk(risk_ident, drivers):
    """The (driver, version) pairs from `drivers` whose drivers.json entry lists this TRAC risk."""
    return [(driver, version) for driver, version in drivers if risk_ident in version.trac_risks]


@dataclass
class MatrixRow:
    risk: Risk
    version: object
    controls: list = field(default_factory=list)
    drivers: list = field(default_factory=list)

    @property
    def coverage(self):
        if not self.controls:
            return "unmapped"
        if any(c["coverage"] == Coverage.FULL for c in self.controls):
            return "covered"
        return "partial"


def risk_control_matrix():
    """One row per current risk with its current linked controls and drivers.

    Links to controls or drivers that are retired (or not yet published) are left
    out, so a retired control shows the risk as less covered.
    """
    controls = {c.pk: (c, version) for c, version in current_controls()}
    current = current_drivers()
    drivers = {d.pk: (d, version) for d, version in current}
    risks = current_risks()
    prefetch_related_objects([version for _, version in risks], "control_links", "driver_links")
    rows = []
    for risk, version in risks:
        row = MatrixRow(risk=risk, version=version)
        for link in version.control_links.all():
            if link.control_id in controls:
                control, control_version = controls[link.control_id]
                row.controls.append(
                    {
                        "control": control,
                        "version": control_version,
                        "coverage": link.coverage,
                        "rationale": link.rationale,
                    }
                )
        for link in version.driver_links.all():
            if link.driver_id in drivers:
                driver, driver_version = drivers[link.driver_id]
                row.drivers.append({"driver": driver, "version": driver_version})
        # A driver can also name the risk in drivers.json (its "trac_risks" list).
        linked = {d["driver"].pk for d in row.drivers}
        for driver, driver_version in drivers_naming_risk(risk.ident, current):
            if driver.pk not in linked:
                row.drivers.append({"driver": driver, "version": driver_version})
        rows.append(row)
    return rows


def unlinked_controls(controls, matrix):
    """The (control, version) pairs in `controls` that no risk in `matrix` links to."""
    linked = {c["control"].pk for row in matrix for c in row.controls}
    return [(c, version) for c, version in controls if c.pk not in linked]


def risks_for_control(control, matrix):
    return [row for row in matrix if any(c["control"].pk == control.pk for c in row.controls)]


def risks_for_driver(driver, matrix):
    return [row for row in matrix if any(d["driver"].pk == driver.pk for d in row.drivers)]


# Engine risks (a read-only copy of the risk engine's risks)

LEVEL_ORDER = ("critical", "high", "medium", "low")
IMPACT_ORDER = ("financial_impact", "client_impact", "regulatory_impact")


def _position(value, order):
    return order.index(value.lower()) if value.lower() in order else len(order)


def scoring_tables(risk):
    """The scoring rules as plain tables: [{"heading": str, "rows": [(level, rule text)]}]. Text only, never run."""
    kinds = sorted(risk.impact_scoring, key=lambda kind: (_position(kind, IMPACT_ORDER), kind))
    tables = [("Likelihood", risk.likelihood_scoring)]
    tables += [(kind.replace("_", " ").capitalize(), risk.impact_scoring[kind]) for kind in kinds]
    return [
        {
            "heading": heading,
            "rows": [(level.capitalize(), levels[level] or "No rule") for level in sorted(levels, key=lambda x: _position(x, LEVEL_ORDER))],
        }
        for heading, levels in tables if levels
    ]


def engine_risks_by_domain():
    """[(domain, [(category, [risk, ...]), ...]), ...]. Each risk carries its drivers and scoring tables."""
    links = EngineRiskDriver.objects.select_related("driver").order_by("driver__ident")
    titles = {driver.pk: version.title for driver, version in current_drivers()}
    domains = {}
    for risk in EngineRisk.objects.prefetch_related(Prefetch("driver_links", queryset=links)):
        for kind in DriverKind.values:
            setattr(risk, f"{kind}_drivers", [
                {"driver": link.driver, "title": titles.get(link.driver_id, "")}
                for link in risk.driver_links.all() if link.kind == kind
            ])
        risk.scoring = scoring_tables(risk)
        domains.setdefault(risk.domain, {}).setdefault(risk.category, []).append(risk)
    return [(domain, list(categories.items())) for domain, categories in domains.items()]


def engine_risks_for_driver(driver):
    """The engine risks that name this driver, each with what it feeds there ("likelihood", "impact" or both)."""
    links = driver.engine_risk_links.select_related("engine_risk").order_by(
        "engine_risk__domain", "engine_risk__category", "engine_risk__name"
    )
    kinds = {}
    for link in links:
        kinds.setdefault(link.engine_risk, set()).add(link.kind)
    return [
        {"risk": risk, "feeds": " and ".join(k.label.lower() for k in DriverKind if k.value in found)}
        for risk, found in kinds.items()
    ]
