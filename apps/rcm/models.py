"""Risk and control registers.

Each item is a governed entity (stable ID) with approved versions. Links that a
user sets on an edit form are stored against the version, so they are reviewed
and approved together with the rest of the change:

    risk --covered by--> control
    risk --raised by--> driver

Drivers and engine risks are not edited in the site: they come from the risk engine's files
(see apps/rcm/engine_files.py).
"""

import re

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from apps.core.references import HELP as REFERENCES_HELP, check_references
from apps.core.versioning import GovernedEntity, GovernedVersion, ImmutableVersionError, Status
from apps.platforms.categories import CATEGORY_KEYS
from apps.platforms.models import Platform
from apps.topics.models import Stage, Theme, Topic
from apps.topics.validation import check_stage_or_theme

from . import levels


class IdSequence(models.Model):
    """Monotonic counters for register IDs, so retired IDs are never reused."""

    key = models.CharField(max_length=10, unique=True)
    last = models.PositiveIntegerField(default=0)


class Nature(models.TextChoices):
    PREVENTIVE = "preventive", "Preventive"
    DETECTIVE = "detective", "Detective"


class Method(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTOMATED = "automated", "Automated"
    IT_DEPENDENT = "it_dependent", "IT-dependent manual"


class Frequency(models.TextChoices):
    EVENT = "event", "Per event"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    SEMIANNUAL = "semiannual", "Semiannual"
    ANNUAL = "annual", "Annual"


class Part(models.TextChoices):
    CONFIGURATION = "configuration", "Configuration"
    MONITORING = "monitoring", "Monitoring"


PART_KEYS = frozenset(Part.values)


class Coverage(models.TextChoices):
    FULL = "full", "Full"
    PARTIAL = "partial", "Partial"


# What an ID from the RCM may look like, for example MC-01 or R-MC-01.
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


class RegisterEntity(GovernedEntity):
    ident = models.CharField(max_length=40, unique=True)

    class Meta:
        abstract = True
        ordering = ["ident"]

    def __str__(self):
        return self.ident


OWNER_ROLE_HELP = "The role accountable for this, for example Application owner or Control owner."
NO_OWNER_YET = "Not assigned yet"


class ScopedVersion(GovernedVersion):
    """Fields shared by risks and controls."""

    title = models.CharField(max_length=160)
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="+")
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    theme = models.ForeignKey(
        Theme, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="For items that apply across the whole lifecycle instead of one stage.",
    )
    owner_role = models.CharField(max_length=120, help_text=OWNER_ROLE_HELP)
    review_by = models.DateField(null=True, blank=True, help_text="Date this must be reviewed again.")

    class Meta(GovernedVersion.Meta):
        abstract = True

    def clean(self):
        super().clean()
        check_stage_or_theme(self)


class Control(RegisterEntity):
    def get_absolute_url(self):
        return reverse("rcm:control", args=[self.ident])

    def get_list_url(self):
        return f'{reverse("rcm:explorer")}?view=controls'


class ControlVersion(ScopedVersion):
    entity = models.ForeignKey(Control, on_delete=models.PROTECT, related_name="versions")
    why = models.TextField(help_text="Why this control exists, in two or three sentences.")
    nature = models.CharField(max_length=12, choices=Nature.choices)
    method = models.CharField(max_length=14, choices=Method.choices)
    frequency = models.CharField(max_length=12, choices=Frequency.choices)
    level = models.CharField(
        max_length=40,
        default=levels.default_key,
        help_text="How important the control is. The levels are listed in content/controls/levels.yaml.",
    )
    performer_role = models.CharField(
        max_length=120, blank=True, help_text="The role that does the work day to day, for example Database administrator."
    )
    applies_when = models.JSONField(
        default=list, blank=True, help_text="Plain statements; the control applies if any is true."
    )
    criteria = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'What good looks like: [{"name": str, "part": "configuration"|"monitoring"|null, '
            '"items": [str | {"text": str, "sox_only": bool}]}]'
        ),
    )
    steps = models.JSONField(
        default=list,
        blank=True,
        help_text='How to run it: [{"role": str, "text": str, "evidence": str, "part": optional}]',
    )
    reviewer_role = models.CharField(
        max_length=120, blank=True, help_text="The role that checks the work, for example Application owner."
    )
    categories = models.JSONField(default=list, blank=True, help_text="Category keys this control applies to.")
    platforms = models.ManyToManyField(Platform, blank=True, related_name="+")
    references = models.JSONField(default=list, blank=True, help_text=REFERENCES_HELP)

    class Meta(ScopedVersion.Meta):
        pass

    def copy_relations_from(self, base):
        self.platforms.set(base.platforms.all())

    @property
    def has_parts(self):
        return any(g.get("part") for g in self.criteria or []) or any(s.get("part") for s in self.steps or [])

    def clean(self):
        super().clean()
        errors = {}
        if not _is_list_of(self.applies_when, str):
            errors["applies_when"] = "Use a list of statements."
        if not all(_valid_group(g) for g in (self.criteria or [])):
            errors["criteria"] = "Each group needs a name, a valid part, and a list of items."
        if not all(
            isinstance(s, dict) and isinstance(s.get("text"), str) and s.get("part") in (None, "", *PART_KEYS)
            for s in (self.steps or [])
        ):
            errors["steps"] = "Each step needs text and a valid part."
        if not _is_list_of(self.categories, str) or not set(self.categories) <= CATEGORY_KEYS:
            errors["categories"] = "Pick categories from the list."
        if self.level not in levels.keys():
            errors["level"] = f"Pick a level from the list: {', '.join(levels.keys())}."
        if errors:
            raise ValidationError(errors)
        check_references(self.references)


class Risk(RegisterEntity):
    def get_absolute_url(self):
        return reverse("rcm:risk", args=[self.ident])

    def get_list_url(self):
        return reverse("rcm:explorer")


class Driver(RegisterEntity):
    """A risk driver. Its ident is the risk engine's id, for example RD01."""

    def get_absolute_url(self):
        return reverse("rcm:driver", args=[self.ident])

    def get_list_url(self):
        return reverse("rcm:explorer")


INDICATOR_TYPES = ("leading", "lagging")


class DriverVersion(GovernedVersion):
    """A condition that makes risks more likely, for example legacy systems without central sign-in.

    Everything here is filled in by `sync_engine` from the risk engine's driver_mapping.yaml and
    from content/drivers/drivers.json. The site has no form for drivers.
    """

    entity = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="versions")
    title = models.CharField(max_length=160, help_text="drivers.json; the id (for example RD01) when empty.")
    description = models.TextField(blank=True, help_text="The engine's rationale.")
    trigger = models.TextField(blank=True, help_text="From the risk engine, read only.")
    questionnaire_fields = models.JSONField(default=list, blank=True, help_text="From the risk engine, read only.")
    category = models.CharField(max_length=80, blank=True, help_text="drivers.json")
    owner_role = models.CharField(max_length=120, help_text="drivers.json")
    indicators = models.JSONField(
        default=list, blank=True, help_text='drivers.json: [{"type": "leading" or "lagging", "text": str}]'
    )
    trac_risks = models.JSONField(default=list, blank=True, help_text="drivers.json: ids of TRAC risks, for example R-AC-01.")
    review_by = models.DateField(null=True, blank=True, help_text="Date this must be reviewed again.")
    references = models.JSONField(default=list, blank=True, help_text=REFERENCES_HELP)

    class Meta(GovernedVersion.Meta):
        pass

    def clean(self):
        super().clean()
        errors = {}
        if not all(
            isinstance(i, dict) and i.get("type") in INDICATOR_TYPES and isinstance(i.get("text"), str) and i["text"].strip()
            for i in (self.indicators if isinstance(self.indicators, list) else [None])
        ):
            errors["indicators"] = "Each indicator needs a type of leading or lagging, and some text."
        for name in ("questionnaire_fields", "trac_risks"):
            if not _is_list_of(getattr(self, name), str):
                errors[name] = "Use a list of text values."
        if errors:
            raise ValidationError(errors)
        check_references(self.references)


class EngineRisk(models.Model):
    """One risk from the risk engine's files. A read-only copy: the engine owns it, there are no drafts."""

    key = models.SlugField(max_length=240, unique=True, help_text="Made from domain, category and name.")
    domain = models.CharField(max_length=120)
    category = models.CharField(max_length=120)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    example = models.TextField(blank=True)
    likelihood_scoring = models.JSONField(default=dict, blank=True, help_text="Level to rule text. Never evaluated.")
    impact_scoring = models.JSONField(default=dict, blank=True, help_text="Impact type to level to rule text. Never evaluated.")
    framework_mappings = models.JSONField(default=dict, blank=True, help_text="Kept as given; never shown.")
    source_file = models.CharField(max_length=120)

    class Meta:
        ordering = ["domain", "category", "name"]

    def __str__(self):
        return self.name


class DriverKind(models.TextChoices):
    LIKELIHOOD = "likelihood", "Likelihood"
    IMPACT = "impact", "Impact"


class EngineRiskDriver(models.Model):
    """An engine risk names this driver as feeding its likelihood or its impact."""

    engine_risk = models.ForeignKey(EngineRisk, on_delete=models.CASCADE, related_name="driver_links")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="engine_risk_links")
    kind = models.CharField(max_length=10, choices=DriverKind.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["engine_risk", "driver", "kind"], name="engine_risk_driver_once")
        ]


class RiskVersion(ScopedVersion):
    entity = models.ForeignKey(Risk, on_delete=models.PROTECT, related_name="versions")
    statement = models.TextField(help_text="What could go wrong, why, and what it would lead to.")
    in_sox_scope = models.BooleanField(default=False)
    references = models.JSONField(default=list, blank=True, help_text=REFERENCES_HELP)

    class Meta(ScopedVersion.Meta):
        pass

    def clean(self):
        super().clean()
        check_references(self.references)

    def copy_relations_from(self, base):
        RiskControlLink.objects.bulk_create(
            RiskControlLink(risk_version=self, control=link.control, coverage=link.coverage, rationale=link.rationale)
            for link in base.control_links.all()
        )
        RiskDriverLink.objects.bulk_create(
            RiskDriverLink(risk_version=self, driver=link.driver) for link in base.driver_links.all()
        )


class _DraftOnlyLink(models.Model):
    """Link rows can only change while their risk version is a draft."""

    class Meta:
        abstract = True

    def _check_draft(self):
        if self.risk_version.status != Status.DRAFT:
            raise ImmutableVersionError("Links can't change after the risk is submitted.")

    def save(self, *args, **kwargs):
        self._check_draft()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_draft()
        return super().delete(*args, **kwargs)


class RiskControlLink(_DraftOnlyLink):
    risk_version = models.ForeignKey(RiskVersion, on_delete=models.CASCADE, related_name="control_links")
    control = models.ForeignKey(Control, on_delete=models.PROTECT, related_name="risk_links")
    coverage = models.CharField(max_length=8, choices=Coverage.choices, default=Coverage.FULL)
    rationale = models.CharField(max_length=300)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["risk_version", "control"], name="risk_control_once")
        ]


class RiskDriverLink(_DraftOnlyLink):
    risk_version = models.ForeignKey(RiskVersion, on_delete=models.CASCADE, related_name="driver_links")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="risk_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["risk_version", "driver"], name="risk_driver_once")
        ]


class EvidenceRule(GovernedEntity):
    """A house rule shown on every control's checklist, such as screenshot guidance."""

    def __str__(self):
        version = self.current()
        return version.name if version else f"Evidence rule {self.pk}"

    def get_absolute_url(self):
        # Evidence rules have no read page; their edit page shows the workflow buttons.
        return reverse("rcm:evidence_rule_edit", args=[self.pk])

    def get_list_url(self):
        return reverse("rcm:evidence_rules")


class RuleAppliesTo(models.TextChoices):
    ALL = "all", "All controls"
    DETECTIVE = "detective", "Detective controls only"
    PREVENTIVE = "preventive", "Preventive controls only"


class EvidenceRuleVersion(GovernedVersion):
    entity = models.ForeignKey(EvidenceRule, on_delete=models.PROTECT, related_name="versions")
    name = models.CharField(max_length=80)
    applies_to = models.CharField(max_length=12, choices=RuleAppliesTo.choices, default=RuleAppliesTo.ALL)
    items = models.JSONField(default=list)
    position = models.PositiveIntegerField(default=0)

    class Meta(GovernedVersion.Meta):
        pass


def rule_applies(rule_version, control_version):
    if rule_version.applies_to == RuleAppliesTo.ALL:
        return True
    return rule_version.applies_to == control_version.nature


def _valid_item(item):
    if isinstance(item, str):
        return True
    return isinstance(item, dict) and isinstance(item.get("text"), str) and isinstance(item.get("sox_only", False), bool)


def _valid_group(group):
    return (
        isinstance(group, dict)
        and isinstance(group.get("name"), str)
        and group.get("part") in (None, "", *PART_KEYS)
        and isinstance(group.get("items"), list)
        and all(_valid_item(i) for i in group["items"])
    )


def _lock_platforms(instance, action, **kwargs):
    if action.startswith("pre_") and isinstance(instance, ControlVersion) and instance.status != Status.DRAFT:
        raise ImmutableVersionError("Platforms can't change after the control is submitted.")


models.signals.m2m_changed.connect(_lock_platforms, sender=ControlVersion.platforms.through)


def _is_list_of(value, kind):
    return isinstance(value, list) and all(isinstance(v, kind) for v in value)
