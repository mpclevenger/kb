"""Checks the Manage screens: Tech Risk only, edits are saved and logged, and used items cannot be removed."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.accounts.models import UserRole
from apps.manage.models import CatalogChange
from apps.platforms.models import AspectQuestion, Platform
from apps.rcm import services
from apps.topics.models import Stage, Theme, Topic

pytestmark = pytest.mark.django_db
User = get_user_model()
Action = CatalogChange.Action
DUPLICATE_MESSAGE = "A platform with this name already exists."


@pytest.fixture(autouse=True)
def sso(settings):
    settings.AUTH_MODE = "sso"
    settings.SSO_USER_HEADER = "HTTP_X_AUTH_USER"
    settings.SSO_GROUPS_HEADER = "HTTP_X_AUTH_GROUPS"
    settings.SSO_GROUP_ROLE_MAP = "grp-tr:tech_risk,grp-co:control_owner"


class As:
    """A browser signed in through the SSO headers."""

    def __init__(self, username, group, role):
        self.client = Client()
        self.headers = {"HTTP_X_AUTH_USER": username, "HTTP_X_AUTH_GROUPS": group}
        self.user = User.objects.create(username=username)
        UserRole.objects.create(user=self.user, role=role)

    def get(self, url):
        return self.client.get(url, **self.headers)

    def post(self, url, data=None):
        return self.client.post(url, data or {}, **self.headers)


@pytest.fixture
def tr():
    return As("tr", "grp-tr", "tech_risk")


@pytest.fixture
def owner():
    return As("co", "grp-co", "control_owner")


@pytest.fixture
def access():
    call_command("seed_topics")
    return Topic.objects.get(id_prefix="MA")


@pytest.fixture
def aws():
    return Platform.objects.create(name="AWS", categories=["cloud", "identity"], hosting="cloud", position=1)


def topic_data(topic, **extra):
    data = {
        "name": topic.name, "id_prefix": topic.id_prefix, "icon": topic.icon, "summary": topic.summary,
        "position": topic.position, "is_active": "on",
    }
    data.update(extra)
    return data


def create_control(user, topic, **extra):
    return services.create_control(
        user, topic, title="Review", why="Why.", owner_role="IAM", nature="detective", method="manual",
        frequency="quarterly", criteria=[], steps=[], **extra,
    )


def stage_names(topic):
    return list(topic.stages.values_list("name", flat=True))


# Access

URLS = [
    ("manage:index", []),
    ("manage:topic_new", []),
    ("manage:platform_new", []),
    ("manage:aspect_list", []),
    ("manage:aspect_new", []),
]


@pytest.mark.parametrize("name,args", URLS)
def test_only_tech_risk_can_open_pages(name, args, tr, owner):
    assert tr.get(reverse(name, args=args)).status_code == 200
    assert owner.get(reverse(name, args=args)).status_code == 403
    assert Client().get(reverse(name, args=args)).status_code == 403


def test_non_tech_risk_cannot_post(owner, access):
    response = owner.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, name="Hacked"))
    assert response.status_code == 403
    access.refresh_from_db()
    assert access.name != "Hacked"
    assert not CatalogChange.objects.exists()


# Topics

def test_create_topic_logs_change(tr):
    response = tr.post(
        reverse("manage:topic_new"),
        {"name": "Backups", "id_prefix": "BK", "icon": "lock", "summary": "", "position": 20, "is_active": "on"},
    )
    topic = Topic.objects.get(name="Backups")
    assert response.status_code == 302
    assert response.url == reverse("manage:topic_edit", args=[topic.pk])
    assert topic.slug == "backups"
    change = CatalogChange.objects.get()
    assert (change.action, change.object_type, change.object_id, change.actor) == (
        Action.CREATE, "topic", topic.pk, tr.user,
    )
    assert change.changes["id_prefix"] == [None, "BK"]


def test_edit_topic_records_before_and_after(tr, access):
    tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, name="Access", summary="New"))
    access.refresh_from_db()
    assert access.name == "Access"
    change = CatalogChange.objects.get()
    assert change.action == Action.UPDATE
    assert change.changes == {
        "name": ["Access management", "Access"],
        "summary": [change.changes["summary"][0], "New"],
    }


def test_saving_without_changes_writes_nothing(tr, access):
    tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access))
    assert not CatalogChange.objects.exists()


def test_invalid_topic_is_not_saved(tr, access):
    response = tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, id_prefix="a"))
    assert response.status_code == 200
    assert b"2 or 3 capital letters" in response.content
    assert not CatalogChange.objects.exists()


def test_prefix_editable_until_controls_exist(tr, access):
    page = tr.get(reverse("manage:topic_edit", args=[access.pk]))
    assert b"Locked:" not in page.content
    create_control(tr.user, access)
    page = tr.get(reverse("manage:topic_edit", args=[access.pk]))
    assert b"Locked:" in page.content
    tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, id_prefix="ZZ"))
    access.refresh_from_db()
    assert access.id_prefix == "MA"


def test_prefix_locked_by_risks_alone(tr, access):
    services.create_risk(tr.user, access, title="Risk", statement="s", owner_role="IAM")
    page = tr.get(reverse("manage:topic_edit", args=[access.pk]))
    assert b"Locked:" in page.content


def test_deactivate_and_reactivate_topic(tr, access):
    url = reverse("manage:topic_active", args=[access.pk])
    tr.post(url, {"active": "false"})
    access.refresh_from_db()
    assert not access.is_active
    tr.post(url, {"active": "true"})
    access.refresh_from_db()
    assert access.is_active
    actions = list(CatalogChange.objects.order_by("id").values_list("action", "changes"))
    assert actions == [
        (Action.DEACTIVATE, {"is_active": [True, False]}),
        (Action.REACTIVATE, {"is_active": [False, True]}),
    ]


def test_topics_and_platforms_have_no_delete_route(tr, access):
    page = tr.get(reverse("manage:topic_edit", args=[access.pk]))
    assert b"Delete" not in page.content
    assert tr.post(f"/manage/topics/{access.pk}/delete/").status_code == 404


# Stages and themes

def stages_url(topic):
    return reverse("manage:stages", args=[topic.pk])


def test_add_stage_appends_and_logs(tr, access):
    tr.post(stages_url(access), {"action": "add", "name": "Attest"})
    assert stage_names(access)[-1] == "Attest"
    assert list(access.stages.values_list("position", flat=True)) == [1, 2, 3, 4, 5]
    change = CatalogChange.objects.get()
    assert change.object_type == "topic"
    before, after = change.changes["stages"]
    assert after == before + ", Attest"


@pytest.mark.parametrize("name", ["", "   ", "provisioning", "x" * 41])
def test_bad_stage_names_are_rejected(tr, access, name):
    response = tr.post(stages_url(access), {"action": "add", "name": name})
    assert response.status_code == 302
    assert access.stages.count() == 4
    assert not CatalogChange.objects.exists()


def test_rename_stage(tr, access):
    stage = access.stages.get(name="Provisioning")
    tr.post(stages_url(access), {"action": "save", "item": stage.pk, "name": "Grant access", "summary": ""})
    stage.refresh_from_db()
    assert stage.name == "Grant access"
    assert CatalogChange.objects.get().changes["stages"][1].count("Grant access") == 1


def test_edit_stage_summary(tr, access):
    stage = access.stages.get(name="Provisioning")
    payload = {"action": "save", "item": stage.pk, "name": stage.name, "summary": "Grant only what the role needs."}
    tr.post(stages_url(access), payload)
    stage.refresh_from_db()
    assert stage.summary == "Grant only what the role needs."
    page = tr.get(reverse("manage:topic_edit", args=[access.pk]))
    assert "Updated the summary of stage" in page.content.decode()
    change = CatalogChange.objects.get()
    assert change.changes["stage summaries"][1] == "Provisioning: Grant only what the role needs."
    assert "stages" not in change.changes


def test_stage_summary_is_shown_in_the_stage_list(tr, access):
    stage = access.stages.get(name="Provisioning")
    stage.summary = "Grant only what the role needs."
    stage.save()
    html = tr.get(reverse("manage:topic_edit", args=[access.pk])).content.decode()
    assert 'value="Grant only what the role needs."' in html
    assert html.count('name="summary"') >= access.stages.count()


def test_stage_summary_too_long_is_refused(tr, access):
    stage = access.stages.get(name="Provisioning")
    payload = {"action": "save", "item": stage.pk, "name": stage.name, "summary": "x" * 241}
    tr.post(stages_url(access), payload)
    stage.refresh_from_db()
    assert stage.summary == ""
    assert not CatalogChange.objects.exists()


def test_saving_a_stage_without_changes_is_not_logged(tr, access):
    stage = access.stages.get(name="Provisioning")
    tr.post(stages_url(access), {"action": "save", "item": stage.pk, "name": stage.name, "summary": stage.summary})
    assert not CatalogChange.objects.exists()


def test_theme_rows_have_no_summary_field(tr, access):
    Theme.objects.create(topic=access, name="Emergency access", position=1)
    html = tr.get(reverse("manage:topic_edit", args=[access.pk])).content.decode()
    themes = html[html.index('id="sec-themes"'):]
    assert 'name="summary"' not in themes


def test_move_stage_up_and_down_keeps_positions_contiguous(tr, access):
    second = access.stages.get(position=2)
    tr.post(stages_url(access), {"action": "up", "item": second.pk})
    assert stage_names(access)[0] == second.name
    tr.post(stages_url(access), {"action": "down", "item": second.pk})
    assert stage_names(access)[1] == second.name
    assert list(access.stages.values_list("position", flat=True)) == [1, 2, 3, 4]
    assert CatalogChange.objects.count() == 2


def test_moving_first_stage_up_changes_nothing(tr, access):
    first = access.stages.get(position=1)
    tr.post(stages_url(access), {"action": "up", "item": first.pk})
    assert not CatalogChange.objects.exists()


def test_remove_unused_stage_renumbers(tr, access):
    stage = access.stages.get(position=2)
    tr.post(stages_url(access), {"action": "remove", "item": stage.pk})
    assert not Stage.objects.filter(pk=stage.pk).exists()
    assert list(access.stages.values_list("position", flat=True)) == [1, 2, 3]
    assert CatalogChange.objects.get().action == Action.UPDATE


def test_remove_referenced_stage_is_blocked(tr, access):
    stage = access.stages.get(position=2)
    create_control(tr.user, access, stage=stage)
    response = tr.post(stages_url(access), {"action": "remove", "item": stage.pk})
    assert Stage.objects.filter(pk=stage.pk).exists()
    page = tr.get(response.url)
    assert b"Can&#x27;t remove the stage" in page.content
    assert not CatalogChange.objects.exists()


def test_theme_add_rename_move_remove(tr, access):
    themes_url = reverse("manage:themes", args=[access.pk])
    tr.post(themes_url, {"action": "add", "name": "Break glass"})
    theme = access.themes.get(name="Break glass")
    tr.post(themes_url, {"action": "save", "item": theme.pk, "name": "Emergency access"})
    tr.post(themes_url, {"action": "up", "item": theme.pk})
    assert list(access.themes.values_list("position", flat=True)) == list(range(1, access.themes.count() + 1))
    tr.post(themes_url, {"action": "remove", "item": theme.pk})
    assert not Theme.objects.filter(topic=access, name="Emergency access").exists()
    assert CatalogChange.objects.count() == 4
    assert all("themes" in c.changes for c in CatalogChange.objects.all())


def test_remove_referenced_theme_is_blocked(tr, access):
    theme = access.themes.first()
    create_control(tr.user, access, theme=theme)
    tr.post(reverse("manage:themes", args=[access.pk]), {"action": "remove", "item": theme.pk})
    assert Theme.objects.filter(pk=theme.pk).exists()


def test_item_actions_are_post_only(tr, access):
    assert tr.get(stages_url(access)).status_code == 405


def test_item_must_belong_to_topic(tr, access):
    other = Topic.objects.exclude(pk=access.pk).first()
    stage = other.stages.first()
    response = tr.post(stages_url(access), {"action": "remove", "item": stage.pk})
    assert response.status_code == 404
    assert Stage.objects.filter(pk=stage.pk).exists()


# Platforms

def platform_data(**extra):
    data = {"name": "Windows Server", "categories": ["operating_system", "jobs"], "hosting": "on_prem", "runs_on": "",
            "owner": "", "summary": "", "doc_links": "[]", "position": 1, "is_active": "on"}
    data.update(extra)
    return data


def test_create_platform_with_categories_runs_on_and_documentation(tr, aws):
    links = [{"label": "Windows documentation", "url": "https://learn.microsoft.com/windows-server/"}]
    response = tr.post(
        reverse("manage:platform_new"), platform_data(runs_on=aws.pk, doc_links=json.dumps(links))
    )
    assert response.status_code == 302
    platform = Platform.objects.get(name="Windows Server")
    assert platform.categories == ["operating_system", "jobs"] and platform.primary_category == "operating_system"
    assert platform.runs_on == aws and platform.doc_links == links
    change = CatalogChange.objects.get()
    assert change.changes["categories"] == [None, ["operating_system", "jobs"]]
    assert change.changes["runs_on"] == [None, "AWS"]


def test_edit_platform_changes_categories_runs_on_and_documentation(tr, aws):
    other = Platform.objects.create(name="Azure", categories=["cloud"])
    link = [{"label": "AWS documentation", "url": "https://docs.aws.amazon.com/"}]
    tr.post(reverse("manage:platform_edit", args=[aws.pk]), platform_data(
        name="AWS", categories=["identity", "cloud"], runs_on=other.pk, doc_links=json.dumps(link)))
    aws.refresh_from_db()
    assert aws.categories == ["identity", "cloud"] and aws.runs_on == other and aws.doc_links == link
    rows = [row for change in CatalogChange.objects.all() for row in change.change_rows]
    assert ("Categories", "cloud, identity", "identity, cloud") in rows
    assert ("Runs on", "(none)", "Azure") in rows
    assert ("Doc links", "(none)", "AWS documentation") in rows


def test_platform_needs_a_category_from_the_list(tr):
    for categories in ([], ["kitchen"]):
        response = tr.post(reverse("manage:platform_new"), platform_data(categories=categories))
        assert response.status_code == 200 and not Platform.objects.exists()
    assert "Select a valid choice" in response.content.decode()


def test_platform_cannot_run_on_itself(tr, aws):
    response = tr.post(reverse("manage:platform_edit", args=[aws.pk]), platform_data(name="AWS", runs_on=aws.pk))
    assert response.status_code == 200 and "A platform can&#x27;t run on itself." in response.content.decode()


@pytest.mark.parametrize("links", [
    [{"label": "", "url": "https://example.com"}],
    [{"label": "Docs", "url": "ftp://example.com"}],
    [{"label": f"Docs {n}", "url": "https://example.com"} for n in range(11)],
])
def test_invalid_documentation_links_are_rejected(tr, links):
    response = tr.post(reverse("manage:platform_new"), platform_data(doc_links=json.dumps(links)))
    assert response.status_code == 200 and not Platform.objects.exists()
    assert "Reference 1" in response.content.decode() or "at most 10" in response.content.decode()


def test_runs_on_choices_are_active_platforms(tr, aws):
    inactive = Platform.objects.create(name="Old", categories=["cloud"], is_active=False)
    html = tr.get(reverse("manage:platform_new")).content.decode()
    assert f'value="{aws.pk}"' in html and f'value="{inactive.pk}"' not in html


def test_platform_form_lists_every_category_and_the_documentation_editor(tr):
    html = tr.get(reverse("manage:platform_new")).content.decode()
    assert html.count('name="categories"') == 9 and "Logging and monitoring" in html
    assert "data-rows-editor" in html and "Documentation links" in html and "js/trac-rows.js" in html


def test_manage_lists_platforms_with_categories_and_runs_on(tr, aws):
    Platform.objects.create(name="SQL Server", categories=["database"], runs_on=aws)
    html = tr.get(reverse("manage:index")).content.decode()
    row = html[html.index("SQL Server"):]
    assert 'category-pill category-database' in row[:400] and "AWS" in row[:400]


def test_duplicate_platform_name_is_rejected(tr, aws):
    response = tr.post(reverse("manage:platform_new"), platform_data(name="AWS"))
    assert response.status_code == 200
    assert Platform.objects.filter(name="AWS").count() == 1
    assert DUPLICATE_MESSAGE in response.content.decode()


def test_aspect_delete_asks_for_confirmation_with_a_data_attribute(tr, access):
    question = AspectQuestion.objects.create(topic=access, label="Access", text="Who can log in?")
    html = tr.get(reverse("manage:aspect_edit", args=[question.pk])).content.decode()
    assert 'data-confirm="Delete this question?' in html
    assert "onsubmit" not in html


def test_deactivate_and_reactivate_platform(tr, aws):
    tr.post(reverse("manage:platform_active", args=[aws.pk]), {"active": "false"})
    aws.refresh_from_db()
    assert not aws.is_active
    tr.post(reverse("manage:platform_active", args=[aws.pk]), {"active": "true"})
    aws.refresh_from_db()
    assert aws.is_active
    assert list(CatalogChange.objects.order_by("id").values_list("action", flat=True)) == [
        Action.DEACTIVATE, Action.REACTIVATE,
    ]


# Aspect questions

def test_aspect_question_crud(tr, access):
    tr.post(reverse("manage:aspect_new"), {"topic": access.pk, "label": "Access", "text": "Who can log in?", "position": 1})
    question = AspectQuestion.objects.get()
    tr.post(
        reverse("manage:aspect_edit", args=[question.pk]),
        {"topic": access.pk, "label": "Access", "text": "Who can sign in?", "position": 1},
    )
    question.refresh_from_db()
    assert question.text == "Who can sign in?"
    assert b"Who can sign in?" in tr.get(reverse("manage:aspect_list")).content
    tr.post(reverse("manage:aspect_delete", args=[question.pk]))
    assert not AspectQuestion.objects.exists()
    assert list(CatalogChange.objects.order_by("id").values_list("action", flat=True)) == [
        Action.CREATE, Action.UPDATE, Action.DELETE,
    ]
    deleted = CatalogChange.objects.first()
    assert deleted.changes["text"] == ["Who can sign in?", None]


def test_aspect_delete_needs_post(tr, access):
    question = AspectQuestion.objects.create(topic=access, label="Access", text="Who?")
    assert tr.get(reverse("manage:aspect_delete", args=[question.pk])).status_code == 405


# Change log

def test_index_and_edit_pages_show_history(tr, access):
    tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, name="Access"))
    index = tr.get(reverse("manage:index")).content.decode()
    assert "Recent changes" in index and "Name: Access management" in index
    edit = tr.get(reverse("manage:topic_edit", args=[access.pk])).content.decode()
    assert "Name: Access management" in edit


def test_history_is_per_object(tr, access, aws):
    tr.post(reverse("manage:platform_edit", args=[aws.pk]), platform_data(name="AWS", owner_role="X"))
    page = tr.get(reverse("manage:topic_edit", args=[access.pk])).content.decode()
    assert "No changes yet." in page


def test_catalog_changes_are_append_only(tr, access):
    tr.post(reverse("manage:topic_edit", args=[access.pk]), topic_data(access, name="Access"))
    change = CatalogChange.objects.get()
    change.action = Action.DELETE
    with pytest.raises(TypeError):
        change.save()
    with pytest.raises(TypeError):
        change.delete()
    with pytest.raises(TypeError):
        CatalogChange.objects.update(action=Action.DELETE)
    with pytest.raises(TypeError):
        CatalogChange.objects.all().delete()
    assert CatalogChange.objects.get().action == Action.UPDATE
