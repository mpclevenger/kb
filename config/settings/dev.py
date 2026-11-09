"""Settings for working on your own computer."""

from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = SECRET_KEY or "dev-only-not-secret"  # noqa: F405
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
# Local work: visitors can edit. Set OPEN_MODE_ROLE=read_only to see the site as a visitor does.
OPEN_MODE_ROLE = os.environ.get("OPEN_MODE_ROLE", "tech_risk")  # noqa: F405
# Local work deliberately uses tech_risk above, so the "visitors can edit" warning (trac.W002) is just noise here.
# It stays active in base and prod settings.
SILENCED_SYSTEM_CHECKS = ["trac.W002"]
