"""The change log for the Manage screens: one permanent line for every field Tech Risk changes."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import AppendOnly


def snapshot(obj, fields):
    """The values of `fields` on `obj` as JSON-safe data; related objects become their names."""
    return {f: str(v) if isinstance(v := getattr(obj, f), models.Model) else v for f in fields}


def show(value):
    if value is None:
        return "(none)"
    if value == "":
        return "(empty)"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(item["label"] if isinstance(item, dict) else str(item) for item in value) or "(none)"
    return str(value)


class CatalogChange(AppendOnly):
    """One row per save made through the Manage pages: who changed which topic, platform or question, and how."""

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DEACTIVATE = "deactivate", "Deactivated"
        REACTIVATE = "reactivate", "Reactivated"
        DELETE = "delete", "Deleted"

    class ObjectType(models.TextChoices):
        TOPIC = "topic", "Topic"
        PLATFORM = "platform", "Platform"
        ASPECT_QUESTION = "aspectquestion", "Aspect question"

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    object_type = models.CharField(max_length=20, choices=ObjectType.choices)
    object_id = models.PositiveBigIntegerField()
    object_label = models.CharField(max_length=200)
    action = models.CharField(max_length=12, choices=Action.choices)
    changes = models.JSONField(default=dict, help_text="Field name to [before, after].")

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["object_type", "object_id"])]

    @classmethod
    def record(cls, actor, obj, action, before=None, after=None):
        """Log a change to `obj`. `before` and `after` are snapshots; only the fields that differ are kept."""
        before, after = before or {}, after or {}
        changes = {
            field: [before.get(field), after.get(field)]
            for field in {**before, **after}
            if before.get(field) != after.get(field)
        }
        return cls.objects.create(
            actor=actor,
            object_type=obj._meta.model_name,
            object_id=obj.pk,
            object_label=str(obj)[:200],
            action=action,
            changes=changes,
        )

    @classmethod
    def for_object(cls, obj):
        return cls.objects.filter(object_type=obj._meta.model_name, object_id=obj.pk)

    @property
    def change_rows(self):
        return [
            (field.replace("_", " ").capitalize(), show(before), show(after))
            for field, (before, after) in self.changes.items()
        ]
