"""Checks that each role can do only what it should, and that sign-in works in both modes."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.test import Client, RequestFactory, override_settings

from apps.accounts import permissions as p
from apps.accounts.middleware import AuthModeMiddleware
from apps.accounts.models import UserRole
from apps.accounts.roles import AUDITOR, CONTROL_OWNER, READ_ONLY, TECH_RISK

pytestmark = pytest.mark.django_db
User = get_user_model()

MATRIX = {
    TECH_RISK: dict(view=True, history=True, propose=True, approve=True, admin=True),
    CONTROL_OWNER: dict(view=True, history=False, propose=False, approve=False, admin=False),
    AUDITOR: dict(view=True, history=True, propose=False, approve=False, admin=False),
    READ_ONLY: dict(view=True, history=False, propose=False, approve=False, admin=False),
}


def make_user(name, *roles, **extra):
    user = User.objects.create(username=name, **extra)
    for role in roles:
        UserRole.objects.create(user=user, role=role)
    return user


def results(user):
    return dict(
        view=p.can_view(user),
        history=p.can_view_history(user),
        propose=p.can_propose(user),
        approve=p.can_approve(user),
        admin=p.can_admin(user),
    )


@pytest.mark.parametrize("role", MATRIX)
def test_role_matrix(role):
    user = make_user("u", role)
    assert results(user) == MATRIX[role]
    assert p.user_roles(user) == {role}
    assert p.is_tech_risk(user) == (role == TECH_RISK)


def test_multi_role_union():
    user = make_user("u", CONTROL_OWNER, AUDITOR)
    assert p.user_roles(user) == {CONTROL_OWNER, AUDITOR}
    assert p.can_view_history(user) and not p.can_propose(user)
    assert not p.can_approve(user) and not p.can_admin(user)


def test_no_roles_denied_everywhere():
    assert not any(results(make_user("u")).values())


def test_anonymous_denied_everywhere():
    anon = AnonymousUser()
    assert not any(results(anon).values())
    assert p.user_roles(anon) == set()
    assert not p.is_tech_risk(anon)


def test_superuser_counts_as_tech_risk():
    user = User.objects.create_superuser("root", password="x")
    assert p.is_tech_risk(user)
    assert results(user) == MATRIX[TECH_RISK]


def test_unique_role_per_user():
    from django.db import IntegrityError, transaction

    user = make_user("u", AUDITOR)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserRole.objects.create(user=user, role=AUDITOR)


def test_decorator_allows_and_denies():
    @p.permission_required_for(p.can_approve)
    def approve_view(request):
        return "ok"

    req = RequestFactory().get("/")
    req.user = make_user("tr", TECH_RISK)
    assert approve_view(req) == "ok"
    for user in (make_user("a", AUDITOR), make_user("ro", READ_ONLY), AnonymousUser()):
        req.user = user
        with pytest.raises(PermissionDenied):
            approve_view(req)


@override_settings(AUTH_MODE="open")
def test_open_mode_signs_visitors_in_with_the_open_mode_role():
    client = Client()
    response = client.get("/accounts/whoami/")
    assert response.status_code == 200
    user = User.objects.get(username="open-visitor")
    assert p.user_roles(user) == {TECH_RISK}  # test settings; the real default is read_only
    assert b"open-visitor" in response.content
    client.get("/accounts/whoami/")
    assert User.objects.filter(username="open-visitor").count() == 1


SSO = dict(
    AUTH_MODE="sso",
    SSO_USER_HEADER="HTTP_X_AUTH_USER",
    SSO_NAME_HEADER="HTTP_X_AUTH_NAME",
    SSO_EMAIL_HEADER="HTTP_X_AUTH_EMAIL",
    SSO_GROUPS_HEADER="HTTP_X_AUTH_GROUPS",
    SSO_GROUP_ROLE_MAP="grp-tr:tech_risk, grp-aud:auditor,grp-co:control_owner,bad:nonsense",
)


def sso_headers(user="jdoe", name="Jane Doe", email="jane@example.com", groups=""):
    return {
        "HTTP_X_AUTH_USER": user,
        "HTTP_X_AUTH_NAME": name,
        "HTTP_X_AUTH_EMAIL": email,
        "HTTP_X_AUTH_GROUPS": groups,
    }


@override_settings(**SSO)
def test_sso_creates_user_and_parses_headers():
    client = Client()
    response = client.get("/accounts/whoami/", **sso_headers(groups="grp-aud"))
    assert response.status_code == 200
    user = User.objects.get(username="jdoe")
    assert (user.first_name, user.last_name) == ("Jane", "Doe")
    assert user.email == "jane@example.com"
    assert p.user_roles(user) == {AUDITOR}


@override_settings(**SSO)
def test_sso_multiple_groups_and_unknown_groups():
    Client().get("/accounts/whoami/", **sso_headers(groups="grp-aud, grp-co ,other"))
    assert p.user_roles(User.objects.get(username="jdoe")) == {AUDITOR, CONTROL_OWNER}


@override_settings(**SSO)
@pytest.mark.parametrize("groups", ["", "unmapped", "bad"])
def test_sso_unmapped_gets_read_only(groups):
    Client().get("/accounts/whoami/", **sso_headers(groups=groups))
    assert p.user_roles(User.objects.get(username="jdoe")) == {READ_ONLY}


@override_settings(**SSO)
def test_sso_role_removed_on_group_change():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers(groups="grp-tr,grp-aud"))
    user = User.objects.get(username="jdoe")
    assert p.user_roles(user) == {TECH_RISK, AUDITOR}
    client.get("/accounts/whoami/", **sso_headers(groups="grp-aud"))
    assert p.user_roles(User.objects.get(username="jdoe")) == {AUDITOR}
    client.get("/accounts/whoami/", **sso_headers(groups="nothing"))
    assert p.user_roles(User.objects.get(username="jdoe")) == {READ_ONLY}


@override_settings(**SSO)
def test_sso_updates_name_and_email():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers())
    client.get("/accounts/whoami/", **sso_headers(name="Janet Roe", email="j@example.com"))
    user = User.objects.get(username="jdoe")
    assert (user.first_name, user.last_name, user.email) == ("Janet", "Roe", "j@example.com")


@override_settings(**SSO)
def test_sso_missing_header_is_anonymous():
    client = Client()
    response = client.get("/accounts/whoami/")
    assert b"Not signed in" in response.content
    assert not User.objects.exists()


@override_settings(**SSO)
def test_sso_header_dropped_after_login_is_anonymous():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers())
    assert b"Not signed in" in client.get("/accounts/whoami/").content


@override_settings(**SSO)
def test_sso_identity_change_switches_session_user():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers(user="a", groups="grp-tr"))
    response = client.get("/accounts/whoami/", **sso_headers(user="b", groups="grp-aud"))
    assert b"<dd>b</dd>" in response.content


@override_settings(**SSO)
def test_sso_logs_in_only_on_identity_change(monkeypatch):
    calls = []
    import apps.accounts.middleware as mw

    real = mw.login
    monkeypatch.setattr(mw, "login", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    client = Client()
    for _ in range(3):
        client.get("/accounts/whoami/", **sso_headers())
    assert len(calls) == 1


@override_settings(**SSO)
def test_sso_custom_header_names():
    with override_settings(SSO_USER_HEADER="HTTP_REMOTE_USER", SSO_GROUPS_HEADER="HTTP_GRPS"):
        Client().get(
            "/accounts/whoami/", HTTP_REMOTE_USER="zed", HTTP_GRPS="grp-tr"
        )
    assert p.user_roles(User.objects.get(username="zed")) == {TECH_RISK}


@pytest.mark.parametrize("mode", ["", "OPEN", "saml", None])
def test_invalid_auth_mode_raises(mode):
    with override_settings(AUTH_MODE=mode):
        with pytest.raises(ImproperlyConfigured):
            AuthModeMiddleware(lambda r: None)


@override_settings(AUTH_MODE="open")
def test_context_processor():
    response = Client().get("/accounts/whoami/")
    ctx = response.context
    assert ctx["can_propose"] and ctx["is_tech_risk"]
    assert ctx["auth_mode"] == "open"


@override_settings(**SSO)
def test_context_processor_read_only():
    ctx = Client().get("/accounts/whoami/", **sso_headers()).context
    assert not any(ctx[k] for k in ("is_tech_risk", "can_propose"))


def test_login_page_renders():
    assert Client().get("/accounts/login/").status_code == 200


def test_sync_roles_writes_only_when_roles_differ():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from apps.accounts.middleware import sync_roles

    user = make_user("sync", AUDITOR)
    with CaptureQueriesContext(connection) as same:
        sync_roles(user, {AUDITOR})
    assert not [q for q in same.captured_queries if not q["sql"].startswith("SELECT")]
    sync_roles(user, {READ_ONLY})
    assert p.user_roles(User.objects.get(username="sync")) == {READ_ONLY}


# Single-approver mode, Sign in page, OPEN_MODE_ROLE

SIGN_IN = "/accounts/login/"
STAFF = "/accounts/staff/"

def in_review_version(user):
    from apps.core.tests.support import new_widget

    _, version = new_widget(user)
    version.status = "in_review"
    return version


def test_self_approval_is_off_by_default(settings):
    from apps.core import workflow_rules

    me = make_user("me", TECH_RISK)
    assert settings.ALLOW_SELF_APPROVAL is False
    assert workflow_rules.why_not("approve", in_review_version(me), me) == "You can't approve your own proposal."


def test_self_approval_on_lets_the_proposer_decide(settings):
    from apps.core import workflow_rules

    settings.ALLOW_SELF_APPROVAL = True
    me = make_user("me", TECH_RISK)
    assert workflow_rules.allowed_actions(in_review_version(me), me) >= {"approve", "reject", "withdraw"}


def test_self_approval_never_lets_other_roles_approve(settings):
    from apps.core import workflow_rules

    settings.ALLOW_SELF_APPROVAL = True
    version = in_review_version(make_user("owner", TECH_RISK))
    assert "approve" not in workflow_rules.allowed_actions(version, make_user("ro", READ_ONLY))


def test_check_warns_only_when_self_approval_is_on(settings):
    from django.core.checks import run_checks

    assert "trac.W001" not in [m.id for m in run_checks()]
    settings.ALLOW_SELF_APPROVAL = True
    assert "trac.W001" in [m.id for m in run_checks()]


def test_no_banner_for_anyone(settings):
    settings.ALLOW_SELF_APPROVAL = True
    assert "Test setup" not in Client().get("/").content.decode()


@pytest.fixture
def shared_site(settings):
    """How the live site is set up: visitors are read only."""
    settings.OPEN_MODE_ROLE = READ_ONLY


def top_bar(client):
    page = client.get("/").content.decode()
    return " ".join(page.split("<header")[1].split("</header>")[0].split())


def test_open_mode_role_must_be_a_real_role(settings):
    settings.OPEN_MODE_ROLE = "admin"
    with pytest.raises(ImproperlyConfigured):
        AuthModeMiddleware(lambda request: None)


# Visitors

def test_visitor_is_read_only(shared_site):
    client = Client()
    assert client.get("/").status_code == 200
    assert p.user_roles(User.objects.get(username="open-visitor")) == {READ_ONLY}
    assert "Read only" in top_bar(client) and "Add your name" in top_bar(client)


TECH_RISK_PAGES = ["/review/", "/rcm/", "/manage/", "/workflow/1/item/1/retire/", "/rcm/evidence-rules/"]


@pytest.mark.parametrize("path", TECH_RISK_PAGES)
def test_visitor_cannot_reach_tech_risk_pages(shared_site, path):
    assert Client().get(path).status_code == 403


def test_visitor_cannot_reach_any_new_or_edit_page(shared_site):
    from apps.core.tests.test_url_access import ROUTES

    client = Client()
    edit_pages = [path for name, path in ROUTES if name.endswith(("_new", "_edit"))]
    assert edit_pages
    for path in edit_pages:
        assert client.get(path).status_code == 403, path


@pytest.mark.parametrize("action", ["submit", "approve", "reject", "withdraw", "discard"])
def test_visitor_cannot_use_workflow_buttons(shared_site, action):
    from django.contrib.contenttypes.models import ContentType

    from apps.core.tests.support import new_widget

    _, draft = new_widget(make_user("author", TECH_RISK))
    ctype = ContentType.objects.get_for_model(draft).pk
    assert Client().post(f"/workflow/{ctype}/{draft.pk}/{action}/").status_code in (403, 404)  # drafts are hidden from visitors
    draft.refresh_from_db()
    assert draft.status == "draft"


def test_visitor_can_read_the_main_pages(shared_site):
    client = Client()
    for path in ("/", "/guides/", "/guides/faq/", "/platforms/", "/topics/", "/rcm/sox/"):
        assert client.get(path, follow=True).status_code == 200, path


def test_visitor_can_comment(shared_site):
    from apps.wiki.models import Feedback

    client = Client()
    data = {"path": "/guides/", "label": "Guides", "section": "General", "comment": "Please add an example."}
    assert client.post("/review/comment/", data).status_code == 302
    assert Feedback.objects.get().submitted_by.username == "open-visitor"


# Adding a name

def test_adding_a_name_keeps_the_visitor_read_only(shared_site):
    client = Client()
    assert client.post(SIGN_IN, {"name": "Pat Lee"}).status_code == 302
    assert "Pat Lee · Read only" in top_bar(client).replace("&middot;", "·")
    assert "Change name" in top_bar(client)
    user = User.objects.get(username="open-name-pat-lee")
    assert user.first_name == "Pat Lee"
    assert p.user_roles(user) == {READ_ONLY}
    assert client.get("/review/").status_code == 403


def test_a_posted_role_is_ignored(shared_site):
    client = Client()
    client.post(SIGN_IN, {"name": "Pat", "role": TECH_RISK})
    client.get("/")
    assert p.user_roles(User.objects.get(username="open-name-pat")) == {READ_ONLY}
    assert client.get("/review/").status_code == 403
    assert 'name="role"' not in client.get(SIGN_IN).content.decode()


def test_the_name_is_optional_and_can_be_removed(shared_site):
    client = Client()
    client.post(SIGN_IN, {"name": "Pat"})
    client.post(SIGN_IN, {"name": ""})
    assert "Add your name" in top_bar(client)
    assert "open-visitor" in client.get("/accounts/whoami/").content.decode()


def test_a_name_needs_letters_or_numbers(shared_site):
    response = Client().post(SIGN_IN, {"name": "!!!"})
    assert response.status_code == 200
    assert not User.objects.filter(username__startswith="open-name").exists()


def test_comment_shows_the_visitor_name_in_the_review_queue(shared_site):
    from apps.wiki.models import Feedback

    client = Client()
    client.post(SIGN_IN, {"name": "Pat Lee"})
    client.get("/")
    Feedback.objects.create(
        submitted_by=User.objects.get(username="open-name-pat-lee"), comment="Hi", about_url="/", about_label="Home", section="Page"
    )
    User.objects.create_superuser("owner", password="pw")
    owner_client = Client()
    assert owner_client.post(STAFF, {"username": "owner", "password": "pw"}).status_code == 302
    assert "Pat Lee" in owner_client.get("/review/").content.decode()


# Tech Risk sign-in (open mode)

def test_superuser_signs_in_and_stays_tech_risk(shared_site):
    User.objects.create_superuser("owner", password="pw")
    client = Client()
    client.get("/")  # becomes a visitor first, like a real browser
    assert client.post(STAFF, {"username": "owner", "password": "pw"}).status_code == 302
    for _ in range(2):
        assert client.get("/review/").status_code == 200
    assert "owner &middot; Tech Risk" in " ".join(client.get("/").content.decode().split())
    assert "Tech Risk sign-in" not in client.get("/").content.decode()


def test_tech_risk_user_signs_in(shared_site):
    user = make_user("tr", TECH_RISK)
    user.set_password("pw")
    user.save()
    client = Client()
    assert client.post(STAFF, {"username": "tr", "password": "pw"}).status_code == 302
    assert client.get("/review/").status_code == 200


def test_read_only_account_is_refused(shared_site):
    user = make_user("ro", READ_ONLY)
    user.set_password("pw")
    user.save()
    client = Client()
    response = client.post(STAFF, {"username": "ro", "password": "pw"})
    assert response.status_code == 200 and "Only Tech Risk accounts" in response.content.decode()
    assert client.get("/review/").status_code == 403


def test_wrong_password_is_refused(shared_site):
    User.objects.create_superuser("owner", password="pw")
    client = Client()
    assert client.post(STAFF, {"username": "owner", "password": "nope"}).status_code == 200
    assert client.get("/review/").status_code == 403


def test_visitor_accounts_cannot_use_the_password_page(shared_site):
    client = Client()
    client.get("/")  # creates open-visitor, which has no usable password
    assert client.post(STAFF, {"username": "open-visitor", "password": ""}).status_code == 200


def test_sign_out_goes_back_to_visitor(shared_site):
    User.objects.create_superuser("owner", password="pw")
    client = Client()
    client.post(STAFF, {"username": "owner", "password": "pw"})
    assert client.get("/review/").status_code == 200
    assert client.get("/accounts/logout/").status_code == 405  # sign-out is POST only
    assert client.post("/accounts/logout/").status_code == 302
    assert client.get("/review/").status_code == 403
    assert "Add your name" in top_bar(client)


def test_staff_page_and_footer_link(shared_site):
    page = Client().get("/").content.decode()
    assert "Tech Risk sign-in" in page and "/accounts/staff/" in page
    assert Client().get(STAFF).status_code == 200


def test_staff_page_is_not_found_in_sso_mode(sso):
    client = Client()
    assert client.get(STAFF, HTTP_X_AUTH_USER="u").status_code == 404
    assert client.post(STAFF, {"username": "a", "password": "b"}, HTTP_X_AUTH_USER="u").status_code == 404
    assert "Tech Risk sign-in" not in client.get("/", HTTP_X_AUTH_USER="u").content.decode()


# SSO: TECH_RISK_USERS

@override_settings(**SSO, TECH_RISK_USERS="Boss, second.person")
def test_tech_risk_users_get_tech_risk_in_sso_mode():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers(user="boss", groups="grp-aud"))
    assert p.user_roles(User.objects.get(username="boss")) == {TECH_RISK, AUDITOR}
    client.get("/accounts/whoami/", **sso_headers(user="SECOND.PERSON"))
    assert p.user_roles(User.objects.get(username="SECOND.PERSON")) == {TECH_RISK}


@override_settings(**SSO, TECH_RISK_USERS="boss")
def test_other_sso_users_stay_read_only_and_lose_tech_risk_when_removed():
    client = Client()
    client.get("/accounts/whoami/", **sso_headers(user="pat"))
    assert p.user_roles(User.objects.get(username="pat")) == {READ_ONLY}
    client.get("/accounts/whoami/", **sso_headers(user="boss"))
    assert p.user_roles(User.objects.get(username="boss")) == {TECH_RISK}
    with override_settings(TECH_RISK_USERS=""):
        client.get("/accounts/whoami/", **sso_headers(user="boss"))
    assert p.user_roles(User.objects.get(username="boss")) == {READ_ONLY}


# System check

def test_check_warns_when_visitors_are_not_read_only(settings):
    from django.core.checks import run_checks

    settings.OPEN_MODE_ROLE = TECH_RISK
    warning = next(m for m in run_checks() if m.id == "trac.W002")
    assert "Visitors get the tech_risk role without signing in" in warning.msg
    settings.OPEN_MODE_ROLE = READ_ONLY
    assert "trac.W002" not in [m.id for m in run_checks()]
    settings.OPEN_MODE_ROLE = TECH_RISK
    settings.AUTH_MODE = "sso"
    assert "trac.W002" not in [m.id for m in run_checks()]
