"""Settings for the live site."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o  # noqa: F405
]
