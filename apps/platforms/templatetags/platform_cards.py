"""Draws the category cards (with their platform chips) shown on the home page and Library."""

from django import template
from django.utils.text import slugify

from apps.platforms.categories import GROUPS
from apps.platforms.models import Platform

register = template.Library()


@register.inclusion_tag("platforms/_category_cards.html")
def category_cards():
    """The category card grid in two groups. A card lists the platforms in its category as chips;
    a platform on several categories appears on each of their cards."""
    members = {}
    for platform in Platform.objects.filter(is_active=True):
        for key in platform.categories:
            members.setdefault(key, []).append(platform)
    return {
        "groups": [
            {
                "title": title,
                "id": slugify(title),
                "cards": [{"category": c, "platforms": members.get(c.value, [])} for c in categories],
            }
            for title, categories in GROUPS
        ],
    }
