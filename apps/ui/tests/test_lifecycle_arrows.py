"""Checks the clickable stage arrows on topic pages."""

import re

import pytest
from django.template import Context, Template

STAGES = [{"id": i, "name": f"Stage {i}", "url": f"/s/{i}/"} for i in range(1, 6)]


def render(active_id, stages=STAGES):
    source = '{% load trac_ui %}{% lifecycle_arrows stages active_id "#panel" %}'
    return Template(source).render(Context({"stages": stages, "active_id": active_id}))


def test_arrows_are_numbered_links_with_htmx_attributes():
    html = render(1)
    assert '<span class="lifecycle-arrow-num">2</span> Stage 2' in html
    assert 'href="/s/2/" hx-get="/s/2/" hx-target="#panel"' in html


def test_only_the_active_arrow_is_marked():
    html = render(3)
    assert html.count('aria-current="step"') == 1 and html.count("is-active") == 1
    assert re.search(r'is-active">\s*<a [^>]*aria-current="step"[^>]*><span class="lifecycle-arrow-num">3<', html)


@pytest.mark.parametrize("count,steps", [(2, [1, 4]), (4, [1, 2, 3, 4]), (5, [1, 2, 3, 3, 4])])
def test_every_arrow_has_a_blue_step_from_light_to_deep(count, steps):
    html = render(1, STAGES[:count])
    assert [int(n) for n in re.findall(r"lifecycle-step-(\d)", html)] == steps
