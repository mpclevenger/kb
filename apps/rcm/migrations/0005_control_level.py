"""Replaces a control's key yes/no and scope with one importance level (see content/controls/levels.yaml)."""

from django.db import migrations, models

import apps.rcm.levels


def key_to_level(apps, schema_editor):
    """Key controls become level "key"; every other control becomes "non-key"."""
    ControlVersion = apps.get_model("rcm", "ControlVersion")
    ControlVersion.objects.filter(is_key=True).update(level="key")
    ControlVersion.objects.filter(is_key=False).update(level="non-key")


def level_to_key(apps, schema_editor):
    ControlVersion = apps.get_model("rcm", "ControlVersion")
    ControlVersion.objects.filter(level="key").update(is_key=True)


class Migration(migrations.Migration):

    dependencies = [
        ("rcm", "0004_engine"),
    ]

    operations = [
        migrations.AddField(
            model_name="controlversion",
            name="level",
            field=models.CharField(
                default=apps.rcm.levels.default_key,
                help_text="How important the control is. The levels are listed in content/controls/levels.yaml.",
                max_length=40,
            ),
        ),
        migrations.RunPython(key_to_level, level_to_key),
        migrations.RemoveField(model_name="controlversion", name="is_key"),
        migrations.RemoveField(model_name="controlversion", name="scope"),
    ]
