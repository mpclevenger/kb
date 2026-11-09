"""The draft, review and publish engine behind every page, control and risk.

In everyday words: a published version is never changed; an edit always makes a new version.
Technical detail follows.

A governed item is a stable entity plus a chain of numbered versions. Content on
a version can only change while it is a draft. Every other change moves a
version through the workflow below, or creates a new version.

    draft -> in_review -> approved -> published
      ^          |
      +----------+ (withdraw)          in_review -> rejected

Retiring an item is a new version of kind "retire" that follows the same
workflow. What is "current" at any moment is the latest published version whose
effective_from has passed.

Concrete subclasses:
    class Risk(GovernedEntity): ...
    class RiskVersion(GovernedVersion):
        entity = models.ForeignKey(Risk, on_delete=models.PROTECT, related_name="versions")
        title = models.CharField(...)
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.dispatch import Signal
from django.utils import timezone

version_transitioned = Signal()


def _now():
    return timezone.now()


class Status(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In review"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class Kind(models.TextChoices):
    CHANGE = "change", "Change"
    RETIRE = "retire", "Retire"


OPEN_STATUSES = (Status.DRAFT, Status.IN_REVIEW, Status.APPROVED)

WORKFLOW_FIELDS = frozenset(
    {
        "id",
        "entity",
        "number",
        "kind",
        "status",
        "proposed_by",
        "proposed_at",
        "submitted_at",
        "decided_by",
        "decided_at",
        "decision_comment",
        "published_by",
        "published_at",
        "effective_from",
    }
)


class TransitionNotAllowed(ValidationError):
    pass


class ImmutableVersionError(ValidationError):
    pass


def _perms():
    from apps.accounts import permissions

    return permissions


class GovernedEntity(models.Model):
    created_at = models.DateTimeField(default=_now, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        abstract = True

    def _published(self):
        return self.versions.filter(status=Status.PUBLISHED)

    def version_as_of(self, when=None):
        when = when or _now()
        return (
            self._published()
            .filter(effective_from__lte=when)
            .order_by("-effective_from", "-number")
            .first()
        )

    def current(self, when=None):
        """Latest effective published version, or None if never published."""
        return self.version_as_of(when)

    def is_retired(self, when=None):
        version = self.version_as_of(when)
        return version is not None and version.kind == Kind.RETIRE

    def open_proposal(self):
        return self.versions.filter(status__in=OPEN_STATUSES).first()

    def history(self):
        return self.versions.order_by("number")


class GovernedVersion(models.Model):
    number = models.PositiveIntegerField(editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CHANGE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    change_summary = models.CharField(max_length=500, blank=True)

    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    proposed_at = models.DateTimeField(default=_now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "number"],
                name="%(app_label)s_%(class)s_unique_number",
            ),
            models.UniqueConstraint(
                fields=["entity"],
                condition=models.Q(status__in=["draft", "in_review", "approved"]),
                name="%(app_label)s_%(class)s_one_open_proposal",
            ),
        ]

    @classmethod
    def content_field_names(cls):
        return [
            f.name
            for f in cls._meta.concrete_fields
            if f.name not in WORKFLOW_FIELDS
        ]

    def content(self):
        return {name: getattr(self, name) for name in self.content_field_names()}

    def copy_relations_from(self, base):
        """Copy related rows (links, child lists) from `base`. Override when needed."""

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.get(pk=self.pk)
            if stored.status != Status.DRAFT:
                changed = [
                    name
                    for name in self.content_field_names()
                    if getattr(stored, name) != getattr(self, name)
                ]
                if changed:
                    raise ImmutableVersionError(
                        f"Content can't change after submission: {', '.join(changed)}"
                    )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != Status.DRAFT:
            raise ImmutableVersionError("Only drafts can be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.entity} v{self.number} ({self.get_status_display()})"


def _require(check, user, message):
    if not check(user):
        raise PermissionDenied(message)


def _require_allowed(action, version, user):
    from . import workflow_rules

    message = workflow_rules.why_not(action, version, user)
    if message:
        raise PermissionDenied(message)


def _transition(version, to_status, user, comment="", **updates):
    from_status = version.status
    version.status = to_status
    for field, value in updates.items():
        setattr(version, field, value)
    version.save()
    version_transitioned.send(
        sender=type(version),
        version=version,
        from_status=from_status,
        to_status=to_status,
        user=user,
        comment=comment,
    )
    return version


def _lock_entity(entity):
    type(entity).objects.select_for_update().get(pk=entity.pk)


def _next_number(entity):
    return (entity.versions.aggregate(n=Max("number"))["n"] or 0) + 1


def _ensure_no_open_proposal(entity):
    existing = entity.open_proposal()
    if existing is not None:
        raise TransitionNotAllowed(
            f"{entity} already has an open proposal (v{existing.number})."
        )


@transaction.atomic
def create_entity(entity_model, version_model, user, entity_fields=None, **content):
    """Create a new entity and its first draft version."""
    _require(_perms().can_propose, user, "You can't propose new items.")
    entity = entity_model.objects.create(created_by=user, **(entity_fields or {}))
    version = version_model.objects.create(
        entity=entity, number=1, proposed_by=user, **content
    )
    version_transitioned.send(
        sender=version_model,
        version=version,
        from_status=None,
        to_status=Status.DRAFT,
        user=user,
        comment="",
    )
    return entity, version


@transaction.atomic
def propose_change(entity, user, change_summary="", **content):
    """Start a new draft from the latest published content, with overrides."""
    _require(_perms().can_propose, user, "You can't propose changes.")
    _lock_entity(entity)
    _ensure_no_open_proposal(entity)
    if entity.is_retired():
        raise TransitionNotAllowed(f"{entity} is retired.")
    version_model = entity.versions.model
    base = entity.versions.filter(status=Status.PUBLISHED).order_by("-number").first()
    data = base.content() if base else {}
    data.update(content)
    data["change_summary"] = change_summary
    version = version_model.objects.create(
        entity=entity, number=_next_number(entity), proposed_by=user, **data
    )
    if base is not None:
        version.copy_relations_from(base)
    version_transitioned.send(
        sender=version_model,
        version=version,
        from_status=None,
        to_status=Status.DRAFT,
        user=user,
        comment=change_summary,
    )
    return version


@transaction.atomic
def propose_retirement(entity, user, reason):
    if not reason.strip():
        raise TransitionNotAllowed("A reason is required to retire an item.")
    _require(_perms().can_propose, user, "You can't propose changes.")
    _lock_entity(entity)
    _ensure_no_open_proposal(entity)
    base = entity.versions.filter(status=Status.PUBLISHED).order_by("-number").first()
    if base is None:
        raise TransitionNotAllowed("Only published items can be retired.")
    if base.kind == Kind.RETIRE:
        raise TransitionNotAllowed(f"{entity} is already retired.")
    data = base.content()
    data["change_summary"] = reason
    version_model = entity.versions.model
    version = version_model.objects.create(
        entity=entity,
        number=_next_number(entity),
        kind=Kind.RETIRE,
        proposed_by=user,
        **data,
    )
    version.copy_relations_from(base)
    version_transitioned.send(
        sender=version_model,
        version=version,
        from_status=None,
        to_status=Status.DRAFT,
        user=user,
        comment=reason,
    )
    return version


def update_draft(version, user, **content):
    if version.status != Status.DRAFT:
        raise TransitionNotAllowed("Only drafts can be edited.")
    _require_allowed("edit", version, user)
    allowed = set(version.content_field_names())
    unknown = set(content) - allowed
    if unknown:
        raise TransitionNotAllowed(f"Unknown fields: {', '.join(sorted(unknown))}")
    for field, value in content.items():
        setattr(version, field, value)
    version.save()
    return version


def discard_draft(version, user):
    if version.status != Status.DRAFT:
        raise TransitionNotAllowed("Only drafts can be discarded.")
    _require_allowed("discard", version, user)
    entity = version.entity
    is_first = version.number == 1
    version.delete()
    if is_first and not entity.versions.exists():
        entity.delete()


def submit(version, user):
    if version.status != Status.DRAFT:
        raise TransitionNotAllowed("Only drafts can be submitted.")
    _require_allowed("submit", version, user)
    return _transition(version, Status.IN_REVIEW, user, submitted_at=_now())


def withdraw(version, user):
    if version.status != Status.IN_REVIEW:
        raise TransitionNotAllowed("Only items in review can be withdrawn.")
    _require_allowed("withdraw", version, user)
    return _transition(version, Status.DRAFT, user, submitted_at=None)


def approve(version, user, comment=""):
    if version.status != Status.IN_REVIEW:
        raise TransitionNotAllowed("Only items in review can be approved.")
    _require_allowed("approve", version, user)
    return _transition(
        version,
        Status.APPROVED,
        user,
        comment,
        decided_by=user,
        decided_at=_now(),
        decision_comment=comment,
    )


def reject(version, user, comment):
    if version.status != Status.IN_REVIEW:
        raise TransitionNotAllowed("Only items in review can be rejected.")
    _require_allowed("reject", version, user)
    if not comment.strip():
        raise TransitionNotAllowed("A comment is required to reject.")
    return _transition(
        version,
        Status.REJECTED,
        user,
        comment,
        decided_by=user,
        decided_at=_now(),
        decision_comment=comment,
    )


def publish(version, user, effective_from=None):
    if version.status != Status.APPROVED:
        raise TransitionNotAllowed("Only approved items can be published.")
    _require(_perms().can_approve, user, "You can't publish changes.")
    now = _now()
    return _transition(
        version,
        Status.PUBLISHED,
        user,
        published_by=user,
        published_at=now,
        effective_from=effective_from or now,
    )


def approve_and_publish(version, user, comment="", effective_from=None):
    with transaction.atomic():
        approve(version, user, comment)
        return publish(version, user, effective_from)


def current_versions(entity_model, when=None):
    """The live version of every entity at `when`, in one query, as a list.

    Retired entities are left out. Each version has its `entity` loaded, so callers
    can use `version.entity` without extra queries.
    """
    when = when or _now()
    version_model = entity_model.versions.rel.related_model
    latest = (
        version_model.objects.filter(status=Status.PUBLISHED, effective_from__lte=when)
        .select_related("entity")
        .order_by("entity_id", "-effective_from", "-number")
        .distinct("entity_id")
    )
    return [v for v in latest if v.kind != Kind.RETIRE]


def effective_entities(entity_model, when=None):
    """Entities with a non-retired effective version at `when`."""
    ids = [v.entity_id for v in current_versions(entity_model, when)]
    return entity_model.objects.filter(pk__in=ids)


__all__ = [
    "GovernedEntity",
    "GovernedVersion",
    "Status",
    "Kind",
    "TransitionNotAllowed",
    "ImmutableVersionError",
    "version_transitioned",
    "create_entity",
    "propose_change",
    "propose_retirement",
    "update_draft",
    "discard_draft",
    "submit",
    "withdraw",
    "approve",
    "reject",
    "publish",
    "approve_and_publish",
    "current_versions",
    "effective_entities",
]
