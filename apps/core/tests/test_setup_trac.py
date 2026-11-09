"""manage.py setup_trac: loads a new TRAC's starting content in the right order."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.tests.support import make_user
from apps.platforms.guidance_files import read_folder
from apps.platforms.models import Guidance, GuidanceVersion, Platform
from apps.rcm.models import Driver, DriverVersion, EngineRisk, EvidenceRuleVersion
from apps.topics.models import Topic
from apps.wiki.models import PageVersion
from apps.wiki.starter_guides import load_guides

pytestmark = pytest.mark.django_db


def test_loads_everything_as_drafts_and_can_run_again():
    make_user("lead", "tech_risk")
    call_command("setup_trac", user="lead")
    assert Guidance.objects.count() == len(read_folder().items)
    assert not GuidanceVersion.objects.exclude(status="draft").exists()
    counts = (Topic.objects.count(), Platform.objects.count(), PageVersion.objects.count(), EvidenceRuleVersion.objects.count())
    assert counts[0] and counts[1] and counts[3]
    assert counts[2] == len(load_guides())
    assert Driver.objects.count() == 8 and EngineRisk.objects.count() == 2  # the risk engine files
    assert not DriverVersion.objects.exclude(status="draft").exists()
    assert not PageVersion.objects.exclude(status="draft").exists()

    call_command("setup_trac", user="lead")
    assert counts == (Topic.objects.count(), Platform.objects.count(), PageVersion.objects.count(), EvidenceRuleVersion.objects.count())


@pytest.mark.parametrize("username, roles, message", [
    ("nobody", None, "Sign in to TRAC once"),
    ("reader", ("read_only",), "Use a Tech Risk user"),
])
def test_stops_before_changing_anything_when_the_user_is_wrong(username, roles, message):
    if roles:
        make_user(username, *roles)
    with pytest.raises(CommandError, match=message):
        call_command("setup_trac", user=username)
    assert not Topic.objects.exists()
