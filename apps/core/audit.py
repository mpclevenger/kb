"""Writes one line to the audit log every time a draft changes state."""

from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver

from .models import AuditEvent
from .versioning import version_transitioned


@receiver(version_transitioned)
def record_transition(sender, version, from_status, to_status, user, comment="", **kwargs):
    AuditEvent.objects.create(
        actor=user if user is not None and user.is_authenticated else None,
        content_type=ContentType.objects.get_for_model(version),
        object_id=version.pk,
        entity_type=ContentType.objects.get_for_model(version.entity),
        entity_id=version.entity_id,
        version_number=version.number,
        from_status=from_status or "",
        to_status=to_status,
        comment=comment or "",
    )
