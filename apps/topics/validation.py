"""A rule used by risks, controls and guides: an item belongs to a stage or a theme, never both."""

from django.core.exceptions import ValidationError


def check_stage_or_theme(version):
    """An item sits at one stage, or applies throughout under a theme, never both."""
    errors = {}
    if version.stage_id and version.stage.topic_id != version.topic_id:
        errors["stage"] = "Pick a stage from the selected topic."
    if version.theme_id and version.theme.topic_id != version.topic_id:
        errors["theme"] = "Pick a theme from the selected topic."
    if version.stage_id and version.theme_id:
        errors["theme"] = "Choose a stage or a theme, not both."
    if errors:
        raise ValidationError(errors)
