"""A simple made-up item (Widget) used only to test the draft and approval engine."""

from django.db import models

from apps.core.versioning import GovernedEntity, GovernedVersion


class Widget(GovernedEntity):
    key = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.key


class WidgetVersion(GovernedVersion):
    entity = models.ForeignKey(Widget, on_delete=models.PROTECT, related_name="versions")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)

    class Meta(GovernedVersion.Meta):
        pass
