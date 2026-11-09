"""Makes the signed-in user's roles available to every page."""

from django.conf import settings

from . import permissions
from .middleware import is_visitor
from .roles import ROLE_CHOICES


def roles(request):
    user = getattr(request, "user", None)
    return {
        "is_tech_risk": permissions.is_tech_risk(user),
        "can_propose": permissions.can_propose(user),
        "auth_mode": settings.AUTH_MODE,
        "is_visitor": settings.AUTH_MODE == "open" and is_visitor(user),
        "role_label": ", ".join(label for value, label in ROLE_CHOICES if value in permissions.user_roles(user)),
    }
