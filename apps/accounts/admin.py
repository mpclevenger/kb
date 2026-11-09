"""Lets a site administrator give people roles in Django's built-in admin screen."""

from django.contrib import admin

from .models import UserRole


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")
