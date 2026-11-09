"""Every named URL in the project is checked against the role it needs.

To add a rule, change the lists below. A new URL needs no change here unless it is public,
Tech Risk only, or limited in some other way: it is then expected to be readable by every role.
"""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

from apps.core.tests.support import As, anonymous

pytestmark = pytest.mark.django_db

# Open to everyone, signed in or not.
PUBLIC = {"core:health", "accounts:login", "accounts:staff_login", "accounts:logout", "accounts:whoami", "ui:gallery"}

# Only Tech Risk may open these (besides every *_new and *_edit route, and the whole manage namespace).
TECH_RISK_ONLY = {"workflow:retire", "rcm:explorer", "rcm:engine_risks", "rcm:evidence_rules", "rcm:topic_options", "review:queue", "review:respond"}

# History pages: Tech Risk and auditors.
HISTORY_READERS = {"core:history"}

# Workflow buttons are checked per version by the engine, so only "must be signed in" can be tested with made-up ids.
SIGNED_IN_ONLY_NAMESPACES = {"workflow"}

DENIED = (403,)  # the site answers "forbidden"; it has no sign-in page to redirect to

# SSO group short names from apps/core/tests/support.py
TECH_RISK = "tr"
OTHER_ROLES = ["co", "aud", "ro"]


def walk(patterns, prefix="", namespace=""):
    """Yield (full name, URL path) for every named route, filling path parameters with dummy values."""
    for entry in patterns:
        route = prefix + str(entry.pattern)
        if isinstance(entry, URLResolver):
            if entry.namespace == "admin":
                continue  # Django admin has its own sign-in and is looked after separately
            inner = f"{namespace}:{entry.namespace}" if namespace and entry.namespace else entry.namespace or namespace
            yield from walk(entry.url_patterns, route, inner)
        elif isinstance(entry, URLPattern) and entry.name:
            name = f"{namespace}:{entry.name}" if namespace else entry.name
            path = re.sub(r"<int:\w+>", "1", route)
            path = re.sub(r"<\w+:\w+>", "x", path)
            yield name, "/" + path


ROUTES = sorted(set(walk(get_resolver().url_patterns)))



def kind(name):
    """Which access rule applies to a route name."""
    namespace, _, short = name.rpartition(":")
    if name in PUBLIC:
        return "public"
    if name in TECH_RISK_ONLY:
        return "tech_risk"
    if namespace in SIGNED_IN_ONLY_NAMESPACES:
        return "signed_in"
    if namespace == "manage" or short.endswith(("_new", "_edit")):
        return "tech_risk"
    if name in HISTORY_READERS:
        return "history"
    return "reader"


def request(who, path):
    """GET the page; if the view is POST-only, POST to it instead."""
    response = who.get(path)
    return who.post(path) if response.status_code == 405 else response


@pytest.fixture(autouse=True)
def sso_headers(sso):
    """Sign-in comes from request headers; a request without them is anonymous."""


def test_the_walk_finds_the_routes_of_every_app():
    apps_seen = {name.split(":")[0] for name, _ in ROUTES}
    assert {"core", "accounts", "rcm", "topics", "platforms", "manage", "review", "wiki", "workflow"} <= apps_seen


def routes_of(*kinds):
    """The (name, path) pairs of the given kinds, as pytest parameters with readable ids."""
    return pytest.mark.parametrize(
        "name,path", [route for route in ROUTES if kind(route[0]) in kinds], ids=lambda value: str(value)
    )


@routes_of("tech_risk", "history", "reader", "signed_in")
def test_anonymous_is_turned_away(name, path):
    assert request(anonymous(), path).status_code in DENIED


@routes_of("tech_risk")
def test_tech_risk_only_routes_reject_every_other_role(name, path):
    for group in OTHER_ROLES:
        assert request(As(f"user-{group}", group), path).status_code in DENIED, group


@routes_of("history")
def test_history_routes_allow_auditors_but_not_other_readers(name, path):
    assert request(As("auditor", "aud"), path).status_code not in DENIED
    for group in ("co", "ro"):
        assert request(As(f"user-{group}", group), path).status_code in DENIED, group


@routes_of("reader")
def test_reader_routes_are_open_to_every_role(name, path):
    """Read-only users may view library pages; the page may be missing (404) but never forbidden."""
    for group in [TECH_RISK, *OTHER_ROLES]:
        status = request(As(f"user-{group}", group), path).status_code
        assert status not in DENIED and status < 500, (group, status)
