"""Change a topic's ID prefix and every ID already issued with it (for example CM-01 becomes MC-01).

Meant for before go-live, while IDs aren't yet used outside TRAC. Controls, risks, the ID counters
and drivers' risk lists are all updated in one step, so every link keeps working.
"""

from django.db import transaction

from apps.topics.models import Topic

from .models import Control, DriverVersion, IdSequence, Risk


def _renamed(ident, old, new):
    for start in (f"{old}-", f"R-{old}-"):
        if ident.startswith(start):
            return start.replace(old, new, 1) + ident[len(start):]
    return ident


@transaction.atomic
def rename_prefix(old, new):
    """Rename prefix `old` to `new`. Does nothing if no topic uses `old`. Returns the number of IDs changed."""
    topic = Topic.objects.filter(id_prefix=old).first()
    if topic is None:
        return 0
    if Topic.objects.filter(id_prefix=new).exists():
        raise ValueError(f"Another topic already uses the prefix {new}.")
    changed = 0
    for model in (Control, Risk):
        for item in model.objects.filter(ident__regex=rf"^(R-)?{old}-").only("pk", "ident"):
            item.ident = _renamed(item.ident, old, new)
            item.save(update_fields=["ident"])
            changed += 1
    for key in (old, f"R-{old}"):
        IdSequence.objects.filter(key=key).update(key=key.replace(old, new, 1))
    for version in DriverVersion.objects.exclude(trac_risks=[]).only("pk", "trac_risks"):
        risks = [_renamed(ident, old, new) for ident in version.trac_risks]
        if risks != version.trac_risks:
            DriverVersion.objects.filter(pk=version.pk).update(trac_risks=risks)
    topic.id_prefix = new
    topic.save(update_fields=["id_prefix"])
    return changed


@transaction.atomic
def move_to_topic(old_prefix, new_prefix, titles, themes=()):
    """Move controls and risks with these titles from one topic to another, with new IDs in the new topic.

    Every version moves, and keeps its theme or stage by name in the new topic. `themes` names themes
    the old topic no longer has; they are removed once nothing uses them. Safe to run again.
    Returns the number of controls and risks moved.
    """
    from apps.topics.models import Stage, Theme

    from . import services
    from .models import ControlVersion, RiskVersion

    old = Topic.objects.filter(id_prefix=old_prefix).first()
    new = Topic.objects.filter(id_prefix=new_prefix).first()
    if old is None or new is None:
        return 0
    moved = 0
    for model, version_model, key in ((Control, ControlVersion, new_prefix), (Risk, RiskVersion, f"R-{new_prefix}")):
        for entity in model.objects.filter(ident__startswith=f"{'R-' if model is Risk else ''}{old_prefix}-"):
            latest = version_model.objects.filter(entity=entity).order_by("-number").first()
            if latest is None or latest.topic_id != old.pk or latest.title not in titles:
                continue
            for version in version_model.objects.filter(entity=entity):
                theme = Theme.objects.filter(topic=new, name=version.theme.name).first() if version.theme_id else None
                stage = Stage.objects.filter(topic=new, name=version.stage.name).first() if version.stage_id else None
                version_model.objects.filter(pk=version.pk).update(topic=new, theme=theme, stage=stage)
            old_ident = entity.ident
            entity.ident = services.next_ident(key)
            entity.save(update_fields=["ident"])
            if model is Risk:
                for driver_version in DriverVersion.objects.filter(trac_risks__contains=[old_ident]).only("pk", "trac_risks"):
                    risks = [entity.ident if ident == old_ident else ident for ident in driver_version.trac_risks]
                    DriverVersion.objects.filter(pk=driver_version.pk).update(trac_risks=risks)
            moved += 1
    for name in themes:
        for theme in Theme.objects.filter(topic=old, name=name):
            in_use = any(
                version_model.objects.filter(theme=theme).exists() for version_model in (ControlVersion, RiskVersion)
            )
            if not in_use:
                theme.delete()
    return moved
