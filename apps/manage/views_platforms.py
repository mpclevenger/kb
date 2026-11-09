"""Manage home page and platform pages."""

from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from apps.platforms.models import Platform
from apps.topics.models import Topic

from .common import admin_only, edit_page
from .forms import PlatformForm
from .models import CatalogChange

RECENT_CHANGES = 20


@admin_only
def index(request):
    return render(
        request,
        "manage/index.html",
        {
            "topics": Topic.objects.annotate(stage_count=Count("stages")).order_by("position", "name"),
            "platforms": Platform.objects.select_related("runs_on"),
            "changes": CatalogChange.objects.select_related("actor")[:RECENT_CHANGES],
        },
    )


@admin_only
def platform_edit(request, pk=None):
    platform = get_object_or_404(Platform, pk=pk) if pk else None
    return edit_page(request, PlatformForm, "manage/platform_form.html", "manage:platform_edit", platform)
