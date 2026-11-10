"""Control levels: the levels.yaml loader, the control form, the content files and the explorer."""

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.core.tests.support import control_post, published_control
from apps.rcm import control_files, levels
from apps.rcm.models import Control

pytestmark = pytest.mark.django_db

FOUR = """
levels:
  - {key: key, label: Key, open: true}
  - {key: non-key, label: Non-key, open: false}
  - {key: compensating, label: Compensating, open: false}
  - {key: supporting, label: Supporting, open: false}
"""


@pytest.fixture
def levels_file(tmp_path, monkeypatch):
    """Point the loader at a temporary levels file; returns a function that writes its text."""
    path = tmp_path / "levels.yaml"
    monkeypatch.setattr(levels, "LEVELS_FILE", path)
    levels.clear_cache()

    def write(text):
        path.write_text(text, encoding="utf-8")
        levels.clear_cache()

    yield write
    levels.clear_cache()


# The loader

def test_shipped_file_has_the_four_levels_in_order():
    assert levels.keys() == ["key", "non-key", "compensating", "supporting"]
    assert levels.first_key() == "key" and levels.is_open("key")
    assert not any(levels.is_open(k) for k in ("non-key", "compensating", "supporting"))
    assert levels.label("non-key") == "Non-key"


def test_order_and_open_come_from_the_file(levels_file):
    levels_file("levels:\n  - {key: b, label: B, open: false}\n  - {key: a, label: A, open: true}\n")
    assert levels.keys() == ["b", "a"] and levels.first_key() == "b"
    assert levels.is_open("a") and not levels.is_open("b")
    assert levels.position("b") < levels.position("a")
    assert levels.default_key() == "b"  # the first level that is folded


def test_unknown_level_ranks_last_and_is_folded(levels_file):
    levels_file(FOUR)
    assert levels.position("gone") == 4 and not levels.is_open("gone") and levels.label("gone") == "gone"


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("levels:\n  - {key: a, label: A, open: true}\n  - {key: a, label: Again, open: false}\n", "'a' is used twice"),
        ("levels:\n  - {key: a, open: true}\n", "level 'a' needs a 'label'"),
        ("levels:\n  - {key: a, label: A}\n", "level 'a' needs 'open: true' or 'open: false'"),
        ("levels:\n  - {label: A, open: true}\n", "needs a 'key'"),
        ("levels: []\n", "at least one level"),
        ("levels: [unclosed\n", "isn't valid YAML"),
    ],
)
def test_bad_levels_file_is_explained(levels_file, text, fragment):
    levels_file(text)
    message = levels.problem()
    assert "levels.yaml" in message and fragment in message


def test_missing_levels_file_is_explained(levels_file):
    levels.clear_cache()
    assert "levels.yaml is missing" in levels.problem()


def test_check_controls_reports_a_bad_levels_file(levels_file, tmp_path):
    levels_file("levels:\n  - {key: a, label: A, open: true}\n  - {key: a, label: A, open: true}\n")
    folder = tmp_path / "controls"
    folder.mkdir()
    (folder / "topic.yaml").write_text("topic: Nothing\n", encoding="utf-8")
    report = control_files.read_folder(folder)
    assert any("levels.yaml" in p and "used twice" in p for p in report.problems)


def test_levels_file_is_not_read_as_a_topic_file():
    names = [p.name for p in control_files._topic_files(control_files.DEFAULT_FOLDER)]
    assert "levels.yaml" not in names and names


# Content files

CONTROL = """
topic: Change management
controls:
  - id: MC-01
    title: A control
    why: Because.
    nature: preventive
    method: automated
    frequency: event
    owned_by: Owner
    {extra}
"""


def read(tmp_path, extra):
    call_command("seed_topics")
    (tmp_path / "topic.yaml").write_text(CONTROL.format(extra=extra), encoding="utf-8")
    return control_files.read_folder(tmp_path)


def test_file_level_is_read(tmp_path):
    report = read(tmp_path, "level: supporting")
    assert not report.problems
    assert report.plans[0].controls[0][2]["level"] == "supporting"


def test_unknown_level_in_a_file_names_file_and_control(tmp_path):
    report = read(tmp_path, "level: vital")
    assert any("topic.yaml" in p and "'MC-01'" in p and "field 'level'" in p and "key, non-key" in p for p in report.problems)


def test_missing_level_in_a_file_is_a_problem(tmp_path):
    report = read(tmp_path, "title_note: x".replace("title_note: x", "stage: Release"))
    assert any("field 'level' is missing" in p for p in report.problems)


@pytest.mark.parametrize("old", ["key_control: yes", "scope: required_sox"])
def test_removed_keys_are_rejected_with_advice(tmp_path, old):
    report = read(tmp_path, f"level: key\n    {old}")
    name = old.split(":")[0]
    assert any(f"field '{name}'" in p and "Use 'level'" in p for p in report.problems)
    assert not any("isn't a known field" in p for p in report.problems)


def test_export_writes_level(tmp_path, access, owner, reviewer):
    published_control(access, owner.user, reviewer.user, level="supporting")
    call_command("export_controls", folder=str(tmp_path))
    data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
    assert data["controls"][0]["level"] == "supporting"
    assert "key_control" not in data["controls"][0] and "scope" not in data["controls"][0]


# The form

def test_form_dropdown_lists_levels_in_order(owner):
    html = owner.get(reverse("rcm:control_new")).content.decode()
    select = html[html.index('name="level"'):]
    select = select[: select.index("</select>")]
    assert select.index("Key") < select.index("Non-key") < select.index("Compensating") < select.index("Supporting")


def test_form_dropdown_follows_levels_file(owner, levels_file):
    levels_file("levels:\n  - {key: top, label: Top tier, open: true}\n  - {key: rest, label: The rest, open: false}\n")
    html = owner.get(reverse("rcm:control_new")).content.decode()
    assert "Top tier" in html and "The rest" in html and "Non-key" not in html


def test_level_round_trips_through_edit(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user, level="compensating")
    url = reverse("rcm:control_edit", args=[control.ident])
    assert owner.get(url).context["form"]["level"].value() == "compensating"
    owner.post(url, control_post(access, level="key", change_summary="Promote"))
    assert Control.objects.get(pk=control.pk).versions.get(number=2).level == "key"


def test_model_rejects_a_level_not_in_the_file(owner, reviewer, access):
    from django.core.exceptions import ValidationError

    _, version = published_control(access, owner.user, reviewer.user)
    version.level = "made-up"
    with pytest.raises(ValidationError):
        version.clean()


# Explorer and wording

def test_no_required_for_sox_wording_on_explorer_and_control_pages(owner, reviewer, access):
    control, _ = published_control(access, owner.user, reviewer.user, level="key")
    for url in (reverse("rcm:explorer"), reverse("rcm:explorer") + "?view=controls", control.get_absolute_url()):
        html = owner.get(url).content.decode()
        assert "Required for SOX" not in html and "Recommended for all" not in html


def test_for_sox_apps_label(owner, reviewer, access):
    control, _ = published_control(
        access, owner.user, reviewer.user,
        criteria=[{"name": "A", "items": [{"text": "Encrypted.", "sox_only": True}]}],
    )
    html = owner.get(control.get_absolute_url()).content.decode()
    assert 'class="sox-only-pill">For SOX apps</span>' in html and "SOX only" not in html
