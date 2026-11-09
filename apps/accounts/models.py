"""The table that records which roles each person holds."""

from django.conf import settings
from django.db import models

from .roles import ROLE_CHOICES


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trac_roles"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")
        ]
        ordering = ["user_id", "role"]

    def __str__(self):
        return f"{self.user} - {self.role}"
