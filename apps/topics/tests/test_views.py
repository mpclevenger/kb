"""Checks the topic pages and the lists of risks, controls and guides under each topic."""

import re

import pytest
from django.core.management import call_command
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.roles import TECH_RISK
from apps.core import versioning as v
from apps.core.tests.support import control_fields, make_user
from apps.rcm import services
from apps.rcm.models import Coverage
from apps.topics.models import Stage, Theme, Topic
from apps.platforms.models import Platform
from apps.wiki.models import Faq, FaqVersion
from apps.wiki.tests.support import count_queries

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def topics():
    call_command("seed_topics")


@pytest.fixture
def access():
    return Topic.objects.get(id_prefix="MA")


@pytest.fixture
def author():
    return make_user("author", TECH_RISK)


@pytest.fixture
def approver():
    return make_user("approver", TECH_RISK)


def publish(version, author, approver):
    v.submit(version, author)
    v.approve_and_publish(version, approver)


def stage_of(topic, name):
    return topic.stages.get(name=name)


def add_control(topic, author, approver, stage=None, publish_it=True, platforms=(), **extra):
    entity, version = services.create_control(author, topic, **control_fields(stage=stage, **extra))
    version.platforms.set(platforms)
    if publish_it:
        publish(version, author, approver)
    return entity


def add_risk(topic, author, approver, stage=None, controls=(), publish_it=True, **extra):
    fields = dict(title="Leaver keeps access", statement="Access is not removed.", owner_role="IAM", stage=stage)
    fields.update(extra)
    entity, version = services.create_risk(author, topic, **fields)
    services.set_risk_links(version, author, controls=controls)
    if publish_it:
        publish(version, author, approver)
    return entity


def add_faq(topic, author, approver, question, answer="Yes, always."):
    entity, version = v.create_entity(Faq, FaqVersion, author, question=question, answer=answer, topic=topic)
    publish(version, author, approver)
    return entity


def html(client, *args, **kwargs):
    response = client.get(*args, **kwargs)
    assert response.status_code == 200
    return response.content.decode()


class TestIndex:
    def test_lists_active_topics_with_counts(self, client, access, author, approver):
        add_control(access, author, approver)
        add_control(access, author, approver, title="Another")
        add_risk(access, author, approver)
        page = html(client, reverse("topics:index"))
        assert page.index("Access management") < page.index("Change management")
        assert reverse("topics:detail", args=[access.slug]) in page
        assert "<strong>2</strong> controls" in page
        assert "<strong>1</strong> risk" in page
        assert "<strong>4</strong> stages" in page
        assert page.count('class="topic-tile"') == 11

    def test_hides_inactive_topics(self, client, access):
        Topic.objects.filter(pk=access.pk).update(is_active=False)
        page = html(client, reverse("topics:index"))
        assert "Access management" not in page
        assert page.count('class="topic-tile"') == 10

    def test_drafts_and_retired_not_counted(self, client, access, author, approver):
        add_control(access, author, approver, publish_it=False)
        retired = add_control(access, author, approver, title="Old")
        publish(v.propose_retirement(retired, author, "No longer needed"), author, approver)
        page = html(client, reverse("topics:index"))
        assert "<strong>0</strong> controls" in page.split("Access management", 1)[1].split("</li>", 1)[0]


ARROW_COLORS = ["lifecycle-step-1", "lifecycle-step-2", "lifecycle-step-3", "lifecycle-step-4"]


def panel(page):
    return page.split('<section class="stage-panel')[1].split("</section>")[0]


class TestDetail:
    def test_unknown_slug_404(self, client):
        assert client.get("/topics/no-such-topic/").status_code == 404

    def test_inactive_topic_404(self, client, access):
        Topic.objects.filter(pk=access.pk).update(is_active=False)
        assert client.get(reverse("topics:detail", args=[access.slug])).status_code == 404

    def test_band_and_summary(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert 'band-title' in page and 'Access management</h1>' in page
        assert access.summary in page
        assert reverse("topics:index") in page

    def test_other_topics_excluded(self, client, access, author, approver):
        other = Topic.objects.get(id_prefix="MC")
        add_control(other, author, approver, title="Release approval")
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert "Release approval" not in page

    def test_coverage_line(self, client, access, author, approver):
        control = add_control(access, author, approver)
        add_risk(access, author, approver, title="Covered", controls=[(control, Coverage.FULL, "x")])
        add_risk(access, author, approver, title="Gap")
        page = html(client, reverse("topics:detail", args=[access.slug]))
        summary = page.split('aria-label="Coverage summary"')[1].split("</dl>")[0]
        assert "<dt>Controls</dt><dd>1</dd>" in summary
        assert "<dt>Risks</dt><dd>2</dd>" in summary
        assert "<dt>Unmapped risks</dt><dd>1</dd>" in summary

    def test_themes_section(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert "Applies throughout" in page and "Privileged access" in page
        Theme.objects.filter(topic=access).delete()
        assert "Applies throughout" not in html(client, reverse("topics:detail", args=[access.slug]))

    def test_throughout_groups_items_by_theme(self, client, access, author, approver):
        privileged = access.themes.get(name="Privileged access")
        service = access.themes.get(name="Service accounts")
        add_control(access, author, approver, title="Admin access review", theme=privileged)
        add_risk(access, author, approver, title="Admin misuse", theme=privileged)
        add_control(access, author, approver, title="Draft only", theme=service, publish_it=False)
        page = html(client, reverse("topics:detail", args=[access.slug]))
        throughout = page.split('id="throughout"')[1].split('id="questions"')[0].split('id="everything-heading"')[0]
        assert "These apply at every stage of the lifecycle, not just one." in throughout
        boxes = throughout.split('<section class="topic-theme-box"')[1:]
        by_name = {name: box for box in boxes for name in access.themes.values_list("name", flat=True) if f">{name}</h3>" in box}
        privileged_box = by_name["Privileged access"]
        assert "Admin access review" in privileged_box and "Admin misuse" in privileged_box
        assert "No control yet" not in privileged_box
        assert "Draft only" not in throughout
        assert "No control yet" in by_name["Service accounts"]
        assert "No control yet" in by_name["Segregation of duties"]

    def test_throughout_whole_topic_box(self, client, access, author, approver):
        url = reverse("topics:detail", args=[access.slug])
        assert "Across the whole topic" not in html(client, url)
        add_control(access, author, approver, title="Topic-wide control")
        add_risk(access, author, approver, title="Topic-wide risk")
        add_control(access, author, approver, title="Staged control", stage=stage_of(access, "Provisioning"))
        add_control(access, author, approver, title="Themed control", theme=access.themes.first())
        page = html(client, url)
        whole = page.split('id="whole-topic"')[1].split("</section>")[0]
        for title in ("Topic-wide control", "Topic-wide risk"):
            assert title in whole
        assert "Staged control" not in whole and "Themed control" not in whole
        assert "No control yet" not in whole

    def test_faq_section(self, client, access, author, approver):
        url = reverse("topics:detail", args=[access.slug])
        assert "Common questions" not in html(client, url)
        add_faq(access, author, approver, "Do service accounts need review?", "Yes, every year.")
        add_faq(Topic.objects.get(id_prefix="MC"), author, approver, "Who approves releases?")
        page = html(client, url)
        assert "Common questions" in page
        assert "<summary>Do service accounts need review?</summary>" in page
        assert "Yes, every year." in page
        assert "Who approves releases?" not in page

    def test_topic_without_stages(self, client, author, approver):
        networking = Topic.objects.get(id_prefix="NW")
        add_control(networking, author, approver, title="VPN access")
        page = html(client, reverse("topics:detail", args=[networking.slug]))
        assert "The stages for this topic are being defined" in page
        assert "The lifecycle" not in page and "lifecycle-arrows" not in page
        assert "VPN access" in page

    def test_no_guides_anywhere(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        for text in ("Guides and how-tos", "Guides", "Standards", "How-tos", "topic-lane-guides"):
            assert text not in page


class TestLifecycle:
    def arrows(self, page):
        return re.findall(r'<li class="lifecycle-arrows-item (lifecycle-step-\d)( is-active)?">', page)

    def test_every_arrow_has_its_own_color_and_the_first_is_selected(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert [step for step, _ in self.arrows(page)] == ARROW_COLORS
        assert [bool(active) for _, active in self.arrows(page)] == [True, False, False, False]
        assert page.count('aria-current="step"') == 1
        assert re.search(r'aria-current="step"><span class="lifecycle-arrow-num">1</span> Roles to permissions', page)
        assert 'class="stage-panel lifecycle-step-1"' in page

    def test_five_stages_use_every_step_in_order(self, client, access):
        Stage.objects.create(topic=access, name="Attest", position=5)
        page = html(client, reverse("topics:detail", args=[access.slug]))
        steps = [int(step[-1]) for step, _ in self.arrows(page)]
        assert steps == sorted(steps) and steps[0] == 1 and steps[-1] == 4 and len(steps) == 5

    def test_arrows_are_links_that_swap_the_lifecycle_with_htmx(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        stage = stage_of(access, "Provisioning")
        link = f'href="/topics/{access.slug}/?stage={stage.pk}" hx-get="/topics/{access.slug}/?stage={stage.pk}" hx-target="#lifecycle-view"'
        assert link in page

    def test_stage_query_switches_the_panel_and_marker(self, client, access, author, approver):
        prov, review = stage_of(access, "Provisioning"), stage_of(access, "Periodic review")
        add_control(access, author, approver, stage=prov, title="Grant access")
        add_control(access, author, approver, stage=review, title="Quarterly review")
        page = html(client, reverse("topics:detail", args=[access.slug]), {"stage": review.pk})
        assert "Quarterly review" in panel(page) and "Grant access" not in panel(page)
        assert [bool(a) for _, a in self.arrows(page)] == [False, False, True, False]
        assert 'class="stage-panel lifecycle-step-3"' in page

    def test_htmx_returns_only_the_lifecycle(self, client, access, author, approver):
        review = stage_of(access, "Periodic review")
        add_control(access, author, approver, stage=review, title="Quarterly review")
        response = client.get(reverse("topics:detail", args=[access.slug]), {"stage": review.pk}, HTTP_HX_REQUEST="true")
        text = response.content.decode()
        assert "<html" not in text and 'id="lifecycle-view"' in text and 'id="everything"' not in text
        assert "Quarterly review" in text and 'class="stage-panel' in text
        assert [bool(a) for _, a in self.arrows(text)] == [False, False, True, False]

    def test_risks_and_controls_in_the_right_stage(self, client, access, author, approver):
        prov = stage_of(access, "Provisioning")
        control = add_control(access, author, approver, stage=prov, title="Grant access")
        add_risk(access, author, approver, stage=prov, title="Excess access granted", controls=[(control, Coverage.FULL, "x")])
        add_control(access, author, approver, stage=stage_of(access, "Periodic review"), title="Quarterly review")
        page = html(client, reverse("topics:detail", args=[access.slug]), {"stage": prov.pk})
        shown = panel(page)
        assert "What can go wrong" in shown and "How we control it" in shown
        assert "Excess access granted" in shown and "Grant access" in shown
        assert "Quarterly review" not in shown
        assert "R-MA-01" in shown and "MA-01" in shown

    def test_empty_stage_says_none_yet(self, client, access):
        shown = panel(html(client, reverse("topics:detail", args=[access.slug])))
        assert shown.count("None yet") == 2

    def test_stage_summary_shown_when_present(self, client, access):
        Stage.objects.filter(pk=stage_of(access, "Provisioning").pk).update(summary="New and changed access.")
        page = html(client, reverse("topics:detail", args=[access.slug]), {"stage": stage_of(access, "Provisioning").pk})
        assert "New and changed access." in panel(page)

    def test_drafts_and_retired_excluded(self, client, access, author, approver):
        prov = stage_of(access, "Provisioning")
        add_control(access, author, approver, stage=prov, title="Draft control", publish_it=False)
        add_risk(access, author, approver, stage=prov, title="Draft risk", publish_it=False)
        gone = add_control(access, author, approver, stage=prov, title="Retired control")
        publish(v.propose_retirement(gone, author, "Obsolete"), author, approver)
        page = html(client, reverse("topics:detail", args=[access.slug]), {"stage": prov.pk})
        for title in ("Draft control", "Draft risk", "Retired control"):
            assert title not in page

    def test_stage_from_other_topic_or_bad_value_falls_back_to_first(self, client, access):
        foreign = Stage.objects.filter(topic__id_prefix="MC").first()
        for value in (foreign.pk, "abc"):
            page = html(client, reverse("topics:detail", args=[access.slug]), {"stage": value})
            assert [bool(a) for _, a in self.arrows(page)] == [True, False, False, False]


@pytest.mark.usefixtures("populated")
class TestEverything:
    @pytest.fixture
    def populated(self, access, author, approver):
        add_control(access, author, approver, stage=stage_of(access, "Provisioning"), title="Grant access")
        add_risk(access, author, approver, stage=stage_of(access, "Provisioning"), title="Excess access granted")

    def test_lists_controls_and_risks_with_type_pills(self, client, access):
        section = html(client, reverse("topics:detail", args=[access.slug])).split('id="everything"')[1]
        assert "Grant access" in section and "Excess access granted" in section
        assert "MA-01" in section and "R-MA-01" in section
        assert '<span class="type-pill type-pill-control">Control</span>' in section
        assert '<span class="type-pill type-pill-risk">Risk</span>' in section

    def test_only_control_and_risk_filters(self, client, access):
        section = html(client, reverse("topics:detail", args=[access.slug])).split('id="everything"')[1]
        chips = re.findall(r'class="topic-chip(?: topic-chip-active)?"', section)
        assert len(chips) == 3
        for label in ("Guides", "Standards", "How-tos"):
            assert label not in section

    def test_type_filter_via_htmx_returns_only_the_list(self, client, access):
        response = client.get(
            reverse("topics:detail", args=[access.slug]), {"type": "risks"}, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="everything"
        )
        text = response.content.decode()
        assert "<html" not in text and 'id="everything"' in text and "lifecycle-view" not in text
        assert "Excess access granted" in text and "Grant access" not in text

    def test_type_links_keep_the_selected_stage(self, client, access):
        review = stage_of(access, "Periodic review")
        section = html(client, reverse("topics:detail", args=[access.slug]), {"stage": review.pk}).split('id="everything"')[1]
        assert f"?stage={review.pk}&amp;type=risks" in section

    def test_bad_type_ignored(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]), {"type": "zzz"})
        assert "Grant access" in page.split('id="everything"')[1]


class TestAppliesTo:
    def row(self, page):
        return page.split('class="applies-to"')[1].split("</p>")[0] if 'class="applies-to"' in page else ""

    def test_hidden_when_no_control_applies_anywhere(self, client, access, author, approver):
        add_control(access, author, approver)
        assert self.row(html(client, reverse("topics:detail", args=[access.slug]))) == ""

    def test_lists_tagged_platforms_and_category_platforms(self, client, access, author, approver):
        tagged = Platform.objects.create(name="Tagged platform", categories=["identity"])
        by_category = Platform.objects.create(name="Database platform", categories=["database"])
        Platform.objects.create(name="Unrelated", categories=["network"])
        Platform.objects.create(name="Retired platform", categories=["database"], is_active=False)
        add_control(access, author, approver, platforms=[tagged])
        add_control(access, author, approver, title="By category", categories=["database"])
        row = self.row(html(client, reverse("topics:detail", args=[access.slug])))
        assert f'href="{tagged.get_absolute_url()}"' in row and "category-identity" in row
        assert f'href="{by_category.get_absolute_url()}"' in row and "category-database" in row
        assert "Unrelated" not in row and "Retired platform" not in row

    def test_unpublished_or_other_topic_controls_do_not_count(self, client, access, author, approver):
        platform = Platform.objects.create(name="Some platform", categories=["identity"])
        add_control(access, author, approver, platforms=[platform], publish_it=False)
        add_control(Topic.objects.get(id_prefix="MC"), author, approver, platforms=[platform])
        assert self.row(html(client, reverse("topics:detail", args=[access.slug]))) == ""


class TestNav:
    def test_review_queue_only_for_approvers(self):
        approver_html = render_to_string("base.html", {"is_tech_risk": True})
        reader_html = render_to_string("base.html", {"is_tech_risk": False})
        assert ">Review queue<" in approver_html
        assert ">Review queue<" not in reader_html
        assert ">Library<" in reader_html

    def test_real_links_and_active_library(self, client, access):
        page = html(client, reverse("topics:detail", args=[access.slug]))
        nav = page.split('aria-label="Primary"')[1].split("</nav>")[0]
        assert 'aria-current="page">Library</a>' in nav
        assert f'href="{reverse("rcm:explorer")}"' in nav

    def test_index_has_library_tabs_with_topic_active(self, client):
        page = html(client, reverse("topics:index"))
        assert f'<a href="{reverse("topics:index")}" aria-current="page">By risk topic</a>' in page

    def test_detail_has_no_library_tabs(self, client, access):
        assert "library-tabs" not in html(client, reverse("topics:detail", args=[access.slug]))

    def test_read_only_user_does_not_see_review_queue(self, client, settings):
        settings.AUTH_MODE = "sso"
        settings.SSO_GROUP_ROLE_MAP = "grp:read_only"
        client.defaults.update(HTTP_X_AUTH_USER="viewer", HTTP_X_AUTH_GROUPS="grp")
        page = html(client, reverse("topics:index"))
        assert "Review queue" not in page


class TestColors:
    def test_count_tiles_use_control_risk_and_alert_colors(self, client, access, author, approver):
        control = add_control(access, author, approver)
        add_risk(access, author, approver, title="Covered", controls=[(control, Coverage.FULL, "x")])
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert '<div class="count-tile count-tile-control"><dt>Controls</dt>' in page
        assert '<div class="count-tile count-tile-risk"><dt>Risks</dt>' in page
        assert '<div class="count-tile count-tile-neutral"><dt>Unmapped risks</dt><dd>0</dd>' in page
        add_risk(access, author, approver, title="Gap")
        page = html(client, reverse("topics:detail", args=[access.slug]))
        assert '<div class="count-tile count-tile-alert"><dt>Unmapped risks</dt><dd>1</dd>' in page


class TestQueryCounts:
    """A topic page runs the same number of queries however many items it lists."""

    def grow(self, topic, author, approver, how_many, stage):
        for n in range(how_many):
            control = add_control(topic, author, approver, stage=stage, title=f"Control {how_many}-{n}")
            add_risk(topic, author, approver, stage=stage, title=f"Risk {how_many}-{n}",
                     controls=[(control, Coverage.FULL, "x")])
            add_faq(topic, author, approver, f"Question {how_many}-{n}?")

    def test_topic_page(self, client, access, author, approver):
        stage = access.stages.first()
        self.grow(access, author, approver, 1, stage)
        url = reverse("topics:detail", args=[access.slug])
        small = count_queries(client, url)
        self.grow(access, author, approver, 4, stage)
        assert count_queries(client, url) == small

    def test_stage_click_runs_fewer_queries_than_the_whole_page(self, client, access, author, approver):
        stage = access.stages.first()
        self.grow(access, author, approver, 3, stage)
        url = reverse("topics:detail", args=[access.slug])
        whole_page = count_queries(client, url)
        assert count_queries(client, f"{url}?stage={stage.pk}", HTTP_HX_REQUEST="true") < whole_page
