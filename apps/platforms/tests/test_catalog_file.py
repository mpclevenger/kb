"""The platform catalog file, content/platforms/catalog.yaml."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.platforms.catalog_file import CATALOG_FILE, read_catalog
from apps.platforms.models import AspectQuestion, Platform

pytestmark = pytest.mark.django_db

SMALL = """\
platforms:
  - name: Windows Server
    categories: [operating_system]
    hosting: on_prem
  - name: SQL Server
    categories: [database, jobs]
    runs_on: Windows Server
    docs: https://example.com/sql
aspects:
  - topic: AC
    label: Access
    question: Who can log in?
"""


@pytest.fixture
def topics(db):
    call_command("seed_topics")


def small_catalog(tmp_path, text=SMALL):
    path = tmp_path / "catalog.yaml"
    path.write_text(text, encoding="utf-8")
    return read_catalog(path)


def test_the_shipped_catalog_is_valid(topics):
    catalog = read_catalog()
    assert catalog.problems == []
    assert len(catalog.platforms) == 12 and len(catalog.aspects) == 10
    kubernetes = next(p for p in catalog.platforms if p["name"] == "Kubernetes")
    assert kubernetes["hosting"] == "hybrid"


def test_a_small_catalog_is_read(topics, tmp_path):
    catalog = small_catalog(tmp_path)
    assert catalog.problems == []
    assert catalog.platforms[1] == {
        "name": "SQL Server", "categories": ["database", "jobs"], "hosting": "",
        "runs_on": "Windows Server", "docs": "https://example.com/sql",
    }
    assert catalog.aspects == [{"topic": "AC", "label": "Access", "question": "Who can log in?"}]


@pytest.mark.parametrize("old, new, fragment", [
    ("categories: [operating_system]", "categories: [os]", "catalog.yaml, platform Windows Server: 'categories' needs at least one of"),
    ("hosting: on_prem", "hosting: moon", "hosting 'moon' isn't allowed"),
    ("runs_on: Windows Server", "runs_on: Nowhere", "runs_on 'Nowhere' isn't another platform"),
    ("docs: https://example.com/sql", "docs: example.com", "'docs' should be a web link"),
    ("topic: AC", "topic: ZZ", "'ZZ' isn't a topic ID prefix on this site"),
    ("label: Access", "lable: Access", "'lable' isn't a known field"),
])
def test_mistakes_get_plain_messages(topics, tmp_path, old, new, fragment):
    catalog = small_catalog(tmp_path, SMALL.replace(old, new))
    assert any(fragment in problem for problem in catalog.problems), catalog.problems


def test_bad_yaml_and_wrong_shape(topics, tmp_path):
    assert "isn't valid YAML" in small_catalog(tmp_path, "platforms: [oops").problems[0]
    assert "expected two lists" in small_catalog(tmp_path, "platforms: []").problems[0]


def test_seed_creates_from_the_file_and_links_runs_on(topics):
    call_command("seed_platforms")
    windows = Platform.objects.get(name="Windows Server")
    assert Platform.objects.get(name="SQL Server").runs_on == windows
    assert Platform.objects.get(name="Kubernetes").hosting == "hybrid"
    assert Platform.objects.get(name="AWS").position == 1
    assert AspectQuestion.objects.get(label="Access").position == 1


def test_seed_needs_topics_and_a_good_file(db, monkeypatch, tmp_path):
    with pytest.raises(CommandError, match="Run seed_topics first"):
        call_command("seed_platforms")
    call_command("seed_topics")
    bad = tmp_path / "catalog.yaml"
    bad.write_text(SMALL.replace("hosting: on_prem", "hosting: moon"), encoding="utf-8")
    monkeypatch.setattr("apps.platforms.management.commands.seed_platforms.read_catalog", lambda: read_catalog(bad))
    with pytest.raises(CommandError, match="Nothing was changed"):
        call_command("seed_platforms")
    assert not Platform.objects.exists()


def test_catalog_file_location():
    assert CATALOG_FILE.name == "catalog.yaml" and CATALOG_FILE.parent.name == "platforms"
