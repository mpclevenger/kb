"""The shared database tables: the audit log, and the record of which content file
each page, control or risk was last synced with."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Rows in this log are append-only.")

    def delete(self):
        raise TypeError("Rows in this log are append-only.")


class AppendOnly(models.Model):
    """Base for logs whose rows can be added but never changed or removed."""

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise TypeError("Rows in this log are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Rows in this log are append-only.")


class AuditEvent(AppendOnly):
    """One row per workflow transition on a governed version."""

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    version = GenericForeignKey("content_type", "object_id")
    entity_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="+"
    )
    entity_id = models.PositiveBigIntegerField(db_index=True)
    version_number = models.PositiveIntegerField()
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    @classmethod
    def for_entity(cls, entity):
        return cls.objects.filter(
            entity_type=ContentType.objects.get_for_model(entity), entity_id=entity.pk
        )


class ContentSync(models.Model):
    """Which version of a page, control or risk was last brought in from, or written out to, its content file.

    It sits beside the entity, not on the version, because published versions must never change.
    A site edit makes a newer published version than the one recorded here, which is how a sync
    spots it. One row per entity; `apps/core/content_sync.py` reads and writes it.
    """

    entity_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    entity_id = models.PositiveBigIntegerField()
    version_id = models.PositiveBigIntegerField(help_text="The version that matched the file at that sync.")
    source_hash = models.CharField(max_length=64, help_text="SHA-256 of the file's text (or entry) at that sync.")
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["entity_type", "entity_id"], name="one_sync_record_per_entity")]

    def __str__(self):
        return f"{self.entity_type} {self.entity_id} synced at {self.synced_at:%Y-%m-%d}"
