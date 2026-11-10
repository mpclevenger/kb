"""The steps for creating a control, risk or driver (with its ID) and linking risks to controls and drivers."""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core import versioning as v

from .models import (
    Control,
    ControlVersion,
    Driver,
    DriverVersion,
    IdSequence,
    Risk,
    RiskControlLink,
    RiskDriverLink,
    RiskVersion,
)


def next_ident(key, width=2):
    """Next ID for a prefix, e.g. MA-07. Locks the counter row so IDs are unique and never reused."""
    seq, _ = IdSequence.objects.get_or_create(key=key)
    seq = IdSequence.objects.select_for_update().get(pk=seq.pk)
    seq.last += 1
    seq.save(update_fields=["last"])
    return f"{key}-{seq.last:0{width}d}"


@transaction.atomic
def create_control(user, topic, **content):
    ident = next_ident(topic.id_prefix)
    return v.create_entity(Control, ControlVersion, user, {"ident": ident}, topic=topic, **content)


@transaction.atomic
def create_risk(user, topic, **content):
    ident = next_ident(f"R-{topic.id_prefix}")
    return v.create_entity(Risk, RiskVersion, user, {"ident": ident}, topic=topic, **content)


@transaction.atomic
def create_driver(user, ident, **content):
    """A driver takes the risk engine's id (for example RD01), so there is no counter."""
    return v.create_entity(Driver, DriverVersion, user, {"ident": ident}, **content)


@transaction.atomic
def set_risk_links(version, user, controls=(), drivers=()):
    """Replace a draft risk's links. controls: iterable of (Control, coverage, rationale); drivers: iterable of Driver."""
    if version.status != v.Status.DRAFT:
        raise v.TransitionNotAllowed("Only drafts can be edited.")
    if version.proposed_by_id != user.pk:
        raise PermissionDenied("Only the proposer can edit a draft.")
    for link in [*version.control_links.all(), *version.driver_links.all()]:
        link.delete()
    for control, coverage, rationale in controls:
        if not rationale.strip():
            raise v.TransitionNotAllowed(f"Add a reason for linking {control.ident}.")
        RiskControlLink.objects.create(
            risk_version=version, control=control, coverage=coverage, rationale=rationale
        )
    for driver in drivers:
        RiskDriverLink.objects.create(risk_version=version, driver=driver)
    return version
