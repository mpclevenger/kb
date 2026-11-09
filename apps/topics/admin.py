"""Lets a site administrator edit topics, stages and themes in Django's built-in admin screen."""

from django.contrib import admin

from .models import Stage, Theme, Topic


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0


class ThemeInline(admin.TabularInline):
    model = Theme
    extra = 0


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "id_prefix", "icon", "position", "is_active"]
    inlines = [StageInline, ThemeInline]
