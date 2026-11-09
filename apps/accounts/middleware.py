"""Works out who is using the site on every request: a visitor (open mode) or a person
signed in by the company's single sign-on, and which roles they hold."""

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.utils.text import slugify

from .models import UserRole
from .roles import ALL_ROLES, READ_ONLY, TECH_RISK

# Open-mode visitors are users whose username starts with this. Anyone else was signed in with a password.
VISITOR_PREFIX = "open-"
NO_NAME_USERNAME = "open-visitor"
# Session key holding the name a visitor typed on the "Add your name" page.
VISITOR_NAME_KEY = "visitor_name"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def is_visitor(user):
    return user is not None and user.is_authenticated and user.username.startswith(VISITOR_PREFIX)


def comma_list(raw):
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def parse_group_role_map(raw):
    mapping = {}
    for pair in comma_list(raw):
        group, sep, role = pair.partition(":")
        group, role = group.strip(), role.strip()
        if sep and group and role in ALL_ROLES:
            mapping.setdefault(group, set()).add(role)
    return mapping


def sync_roles(user, roles):
    """Make the user's stored roles equal `roles`. Writes only when something differs."""
    current = set(user.trac_roles.values_list("role", flat=True))
    if current == roles:
        return
    user.trac_roles.filter(role__in=current - roles).delete()
    UserRole.objects.bulk_create(
        [UserRole(user=user, role=r) for r in roles - current], ignore_conflicts=True
    )
    user._trac_roles = None


def visitor_user(name):
    """The shared user for visitors with this name (or with no name). Always holds OPEN_MODE_ROLE only."""
    username = f"{VISITOR_PREFIX}name-{slugify(name)}" if name else NO_NAME_USERNAME
    user, _ = get_user_model().objects.get_or_create(username=username, defaults={"password": make_password(None)})
    if user.first_name != name:
        user.first_name = name
        user.save(update_fields=["first_name"])
    sync_roles(user, {settings.OPEN_MODE_ROLE})
    return user


def sso_roles(username, groups_header):
    """Roles from the user's groups (SSO_GROUP_ROLE_MAP) plus TECH_RISK_USERS. No match means read only."""
    mapping = parse_group_role_map(settings.SSO_GROUP_ROLE_MAP)
    roles = set()
    for group in comma_list(groups_header):
        roles |= mapping.get(group, set())
    if username.lower() in [u.lower() for u in comma_list(settings.TECH_RISK_USERS)]:
        roles.add(TECH_RISK)
    return roles or {READ_ONLY}


class AuthModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.mode = settings.AUTH_MODE
        if self.mode not in ("open", "sso"):
            raise ImproperlyConfigured(
                f"AUTH_MODE must be 'open' or 'sso', got {self.mode!r}."
            )
        if settings.OPEN_MODE_ROLE not in ALL_ROLES:
            raise ImproperlyConfigured(
                f"OPEN_MODE_ROLE must be one of {sorted(ALL_ROLES)}, got {settings.OPEN_MODE_ROLE!r}."
            )

    def __call__(self, request):
        if self.mode == "open":
            self.open_mode(request)
        else:
            self.sso_mode(request)
        return self.get_response(request)

    def open_mode(self, request):
        if request.user.is_authenticated and not is_visitor(request.user):
            return  # signed in with a password on the Tech Risk sign-in page: leave them alone
        name = request.session.get(VISITOR_NAME_KEY, "")
        user = visitor_user(name)
        if request.user.pk != user.pk:
            login(request, user, backend=BACKEND)  # signing in as another user clears the session
            if name:
                request.session[VISITOR_NAME_KEY] = name

    def sso_mode(self, request):
        meta = request.META
        username = (meta.get(settings.SSO_USER_HEADER) or "").strip()
        if not username:
            request.user = AnonymousUser()
            return
        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        name = (meta.get(settings.SSO_NAME_HEADER) or "").strip()
        email = (meta.get(settings.SSO_EMAIL_HEADER) or "").strip()
        changed = []
        if name:
            first, _, last = name.partition(" ")
            if (user.first_name, user.last_name) != (first, last):
                user.first_name, user.last_name = first, last
                changed += ["first_name", "last_name"]
        if email and user.email != email:
            user.email = email
            changed.append("email")
        if changed:
            user.save(update_fields=changed)

        sync_roles(user, sso_roles(username, meta.get(settings.SSO_GROUPS_HEADER)))

        if request.user.pk != user.pk:
            login(request, user, backend=BACKEND)
        else:
            request.user = user
