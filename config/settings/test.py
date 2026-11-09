"""Settings used when running the automated tests."""

from .base import *  # noqa: F401,F403

SECRET_KEY = "test-only-not-secret"
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
AUTH_MODE = "open"
INSTALLED_APPS = INSTALLED_APPS + ["apps.core.tests.testapp"]  # noqa: F405
# Most tests act as a Tech Risk visitor; tests of the shared-site setup override this.
OPEN_MODE_ROLE = "tech_risk"
