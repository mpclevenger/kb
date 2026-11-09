"""The site's main settings, shared by local work, tests and the live site."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.ui",
    "apps.topics",
    "apps.platforms",
    "apps.manage",
    "apps.wiki",
    "apps.rcm",
    "apps.review",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.AuthModeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.roles",
                "apps.ui.context_processors.suite",
                "apps.review.context_processors.comment_box",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgres://trac:trac@localhost:5432/trac",
        conn_max_age=60,
    )
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"

# open: visitors are signed in automatically with OPEN_MODE_ROLE; the owner signs in with a password
#       (footer link "Tech Risk sign-in").
# sso: identity and groups come from the platform's SSO headers.
AUTH_MODE = os.environ.get("AUTH_MODE", "open")
# open mode: the role every visitor has (tech_risk, control_owner, auditor, read_only). Visitors cannot pick another.
OPEN_MODE_ROLE = os.environ.get("OPEN_MODE_ROLE", "read_only")
# Single-approver mode: true lets a proposer approve or reject their own proposal.
# Turn it off once a second Tech Risk approver has access.
ALLOW_SELF_APPROVAL = os.environ.get("ALLOW_SELF_APPROVAL", "false").strip().lower() == "true"
SSO_USER_HEADER = os.environ.get("SSO_USER_HEADER", "HTTP_X_AUTH_USER")
SSO_NAME_HEADER = os.environ.get("SSO_NAME_HEADER", "HTTP_X_AUTH_NAME")
SSO_EMAIL_HEADER = os.environ.get("SSO_EMAIL_HEADER", "HTTP_X_AUTH_EMAIL")
SSO_GROUPS_HEADER = os.environ.get("SSO_GROUPS_HEADER", "HTTP_X_AUTH_GROUPS")
# Maps platform group names to TRAC roles, e.g. "grp-techrisk:tech_risk,grp-auditors:auditor"
SSO_GROUP_ROLE_MAP = os.environ.get("SSO_GROUP_ROLE_MAP", "")

# sso mode: usernames (as sent in the SSO user header) that always get Tech Risk, e.g. "jdoe,asmith".
TECH_RISK_USERS = os.environ.get("TECH_RISK_USERS", "")

SUITE_LINKS = {
    "TRAC": "/",
    "TRUST": os.environ.get("TRUST_URL", ""),
    "Risk": os.environ.get("RISK_URL", ""),
    "Initiatives": os.environ.get("INITIATIVES_URL", ""),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
