"""Checks the categories and the starting platforms load correctly and in the right order."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.platforms.categories import CATEGORY_KEYS, GROUPS, HEADINGS, SHARED_SERVICES, STACK, Category, group_title
from apps.platforms.models import Platform

pytestmark = pytest.mark.django_db


EXPECTED_SEED = {
    "AWS": ["cloud", "identity", "database", "operating_system"],
    "Azure": ["cloud", "identity", "database"],
    "Databricks": ["cloud", "database", "jobs"],
    "GitHub Enterprise Server": ["engineering_tools", "jobs"],
    "Splunk": ["logging", "jobs"],
    "SQL Server": ["database", "jobs"],
    "Windows Server": ["operating_system", "jobs"],
    "In-house job scheduler": ["jobs", "application"],
    "Active Directory": ["identity"],
    "Entra ID": ["identity"],
    "Kubernetes": ["cloud"],
    "VPN": ["network"],
}

EXPECTED_DOCS = {
    "AWS": "https://docs.aws.amazon.com/",
    "Azure": "https://learn.microsoft.com/azure/",
    "Databricks": "https://docs.databricks.com/",
    "GitHub Enterprise Server": "https://docs.github.com/en/enterprise-server@latest",
    "Splunk": "https://help.splunk.com/",
    "SQL Server": "https://learn.microsoft.com/sql/sql-server/",
    "Windows Server": "https://learn.microsoft.com/windows-server/",
    "Active Directory": "https://learn.microsoft.com/windows-server/identity/ad-ds/",
    "Entra ID": "https://learn.microsoft.com/entra/",
    "Kubernetes": "https://kubernetes.io/docs/",
}


# Categories

def test_categories_are_ordered_and_grouped():
    assert list(Category.values) == [
        "application", "database", "operating_system", "jobs", "network",
        "identity", "cloud", "engineering_tools", "logging",
    ]
    assert [c for _, group in GROUPS for c in group] == list(Category)
    assert group_title(Category.JOBS) == "The stack" and group_title(Category.LOGGING) == "Shared services"
    assert set(STACK) | set(SHARED_SERVICES) == set(Category) and CATEGORY_KEYS == set(Category.values)


def test_every_category_has_its_page_heading():
    assert set(HEADINGS) == set(Category)
    assert {c.value: c.heading for c in Category} == {
        "application": "A well-controlled application",
        "database": "A well-controlled database",
        "operating_system": "A well-controlled server",
        "jobs": "Well-controlled jobs and interfaces",
        "network": "A well-controlled network",
        "identity": "A well-controlled identity service",
        "cloud": "A well-controlled cloud environment",
        "engineering_tools": "Well-controlled engineering tools",
        "logging": "Well-controlled logging",
    }


# Platform categories

@pytest.mark.parametrize("categories", [[], ["kitchen"], ["cloud", "cloud"], "cloud", [1], None])
def test_platform_categories_are_validated(categories):
    platform = Platform(name="P", categories=categories)
    with pytest.raises(ValidationError) as error:
        platform.full_clean(exclude=["slug"])
    assert "categories" in error.value.message_dict


def test_platform_keeps_category_order_and_first_is_primary():
    platform = Platform(name="P", categories=["jobs", "database"])
    platform.full_clean(exclude=["slug"])
    platform.save()
    platform.refresh_from_db()
    assert platform.categories == ["jobs", "database"] and platform.primary_category == "jobs"


def test_platform_names_are_unique():
    Platform.objects.create(name="P", categories=["cloud"])
    with pytest.raises(ValidationError) as error:
        Platform(name="P", categories=["cloud"]).full_clean(exclude=["slug"])
    assert error.value.message_dict["name"] == ["A platform with this name already exists."]


def test_platform_slug_comes_from_the_name_and_stays_unique():
    first = Platform.objects.create(name="SQL Server", categories=["database"])
    second = Platform.objects.create(name="SQL  Server!", categories=["database"])
    assert (first.slug, second.slug) == ("sql-server", "sql-server-2")


# Seed

@pytest.fixture
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


def test_seed_creates_platforms_with_categories_in_order(seeded):
    assert {p.name: p.categories for p in Platform.objects.all()} == EXPECTED_SEED


def test_seed_has_no_services_job_servers_or_bastion_hosts(seeded):
    assert not Platform.objects.filter(name="Job servers").exists()
    assert not Platform.objects.filter(name__icontains="bastion").exists()
    assert not Platform.objects.filter(name__in=["RDS", "IAM", "Appliance"]).exists()


def test_seed_runs_on(seeded):
    windows = Platform.objects.get(name="Windows Server")
    runs_on = {p.name: p.runs_on for p in Platform.objects.exclude(runs_on=None)}
    assert runs_on == {"SQL Server": windows, "In-house job scheduler": windows}


def test_seed_documentation_links(seeded):
    for name, url in EXPECTED_DOCS.items():
        assert Platform.objects.get(name=name).doc_links == [{"label": f"{name} documentation", "url": url}], name
    for name in ("In-house job scheduler", "VPN"):
        assert Platform.objects.get(name=name).doc_links == []


def test_seeded_platforms_pass_validation(seeded):
    for platform in Platform.objects.all():
        platform.full_clean()


def test_seed_is_idempotent_and_keeps_edits(seeded):
    Platform.objects.filter(name="VPN").update(owner="Network team", categories=["cloud"])
    Platform.objects.filter(name="SQL Server").update(runs_on=None, doc_links=[])
    count = Platform.objects.count()
    call_command("seed_platforms")
    assert Platform.objects.count() == count
    vpn, sql = Platform.objects.get(name="VPN"), Platform.objects.get(name="SQL Server")
    assert (vpn.owner, vpn.categories) == ("Network team", ["cloud"])
    assert sql.runs_on is None and sql.doc_links == []
