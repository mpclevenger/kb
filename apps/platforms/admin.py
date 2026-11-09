"""Lets a site administrator edit platforms and aspect questions in Django's built-in admin screen."""

from django.contrib import admin

from .models import AspectQuestion, Platform


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "categories", "hosting", "runs_on", "owner", "is_active"]
    list_filter = ["hosting", "is_active"]


@admin.register(AspectQuestion)
class AspectQuestionAdmin(admin.ModelAdmin):
    list_display = ["label", "text", "topic", "position"]
