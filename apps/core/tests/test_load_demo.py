"""manage.py load_demo: a fully published demo that can be loaded again."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import versioning as v
from apps.core.models import AuditEvent
from apps.core.tests.support import make_user
from apps.platforms.guidance_files import read_folder
from apps.platforms.models import Guidance
from apps.rcm.models import Control, ControlVersion, Driver, EngineRisk, Risk
from apps.wiki.models import Faq, FaqVersion, PageVersion

pytestmark = pytest.mark.django_db


from apps.rcm.tests.test_sync_controls import shipped_control_count  # noqa: E402


def counts():
    return {
        model.__name__: model.objects.count()
        for model in (Control, Risk, Driver, EngineRisk, Guidance, Faq, PageVersion, AuditEvent)
    }


def test_loads_everything_published():
    call_command("load_demo")
    assert not PageVersion.objects.exclude(status="published").exists()
    assert Control.objects.count() == shipped_control_count() and Driver.objects.count() == 8 and EngineRisk.objects.count() == 2
    assert all(c.current() for c in Control.objects.all())
    assert all(r.current() for r in Risk.objects.all())
    assert all(d.current() for d in Driver.objects.all())
    # Category and platform guidance comes from content/platforms through setup_trac.
    assert Guidance.objects.count() == len(read_folder().items) and all(g.current() for g in Guidance.objects.all())
    assert Faq.objects.count() == 1 and FaqVersion.objects.get().status == "published"

    assert ControlVersion.objects.filter(title="Periodic user access review", status="published").exists()
    assert "business days" not in json.dumps([c.criteria for c in ControlVersion.objects.all()])
    assert Driver.objects.get(ident="RD01").current().title == "Systems with their own user accounts"


def test_can_run_again_without_duplicating():
    call_command("load_demo")
    before = counts()
    call_command("load_demo")
    assert counts() == before


def test_refuses_in_sso_mode(settings):
    settings.AUTH_MODE = "sso"
    with pytest.raises(CommandError, match="demos only"):
        call_command("load_demo")
    assert not Control.objects.exists()


def test_leaves_other_users_drafts_alone():
    other = make_user("someone-else", "tech_risk")
    call_command("setup_trac", user="someone-else")
    mine = set(PageVersion.objects.filter(proposed_by=other).values_list("pk", flat=True))
    call_command("load_demo")
    assert mine and set(PageVersion.objects.filter(status="draft").values_list("pk", flat=True)) == mine


def test_publishes_are_in_the_audit_log():
    call_command("load_demo")
    version = ControlVersion.objects.get(title="Periodic user access review")
    events = AuditEvent.for_entity(version.entity)
    assert {e.to_status for e in events} >= {v.Status.IN_REVIEW, v.Status.PUBLISHED}
    assert events.filter(actor__username="demo-approver", to_status=v.Status.PUBLISHED).exists()
