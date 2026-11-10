"""Diagrams: the ```mermaid block in guide files, the sanitizer, check_guides and a real browser render."""

import pytest
from django.urls import reverse

from apps.core.tests.support import make_user
from apps.wiki.guide_checks import HELP_LINE, diagram_problems, guide_problems
from apps.wiki.guide_sync import html_to_markdown
from apps.wiki.richtext import clean_html
from apps.wiki.starter_guides import GUIDES_DIR, parse_guide
from apps.wiki.tests.support import make_page

DIAGRAM = (
    "flowchart LR\n"
    "  accTitle: A short title\n"
    "  accDescr: One sentence about the diagram.\n"
    "  A[Request] --> B[Approve]"
)
HEADER = "---\ntitle: A guide\nsection: build\n---\n"


def guide_with(tmp_path, diagram):
    path = tmp_path / "a-guide.md"
    path.write_text(f"{HEADER}An intro.\n\n```mermaid\n{diagram}\n```\n\n## First\n\nText.\n\n{HELP_LINE}\n", encoding="utf-8")
    return parse_guide(path)


# Sanitizer

def test_sanitizer_keeps_the_mermaid_class_on_pre():
    assert clean_html('<pre class="mermaid">flowchart LR\nA --&gt; B</pre>') == '<pre class="mermaid">flowchart LR\nA --&gt; B</pre>'


@pytest.mark.parametrize("html, expected", [
    ('<pre class="other">x</pre>', "<pre>x</pre>"),
    ('<pre class="mermaid other">x</pre>', "<pre>x</pre>"),
    ('<pre class="mermaid" onclick="x()">x</pre>', '<pre class="mermaid">x</pre>'),
    ('<p class="mermaid">x</p>', "<p>x</p>"),
    ('<code class="mermaid">x</code>', "<code>x</code>"),
])
def test_sanitizer_strips_any_other_class_or_attribute(html, expected):
    assert clean_html(html) == expected


def test_sanitizer_still_escapes_markup_inside_a_diagram():
    assert "<script" not in clean_html('<pre class="mermaid"><script>alert(1)</script></pre>')


# Loader

def test_loader_turns_a_mermaid_block_into_an_escaped_pre(tmp_path):
    guide = guide_with(tmp_path, DIAGRAM + '\n\n  B --> C["<b>x</b> & y"]')
    assert guide.body.count('<pre class="mermaid">') == 1
    assert "A[Request] --&gt; B[Approve]" in guide.body
    assert "&lt;b&gt;x&lt;/b&gt; &amp; y" in guide.body and "<b>" not in guide.body
    assert "```" not in guide.body and "<h2" in guide.body


def test_a_blank_line_inside_a_diagram_does_not_split_it(tmp_path):
    guide = guide_with(tmp_path, DIAGRAM + "\n\n  B --> C")
    assert guide.body.count("<pre") == 1 and "B --&gt; C" in guide.body


def test_other_code_blocks_are_unchanged(tmp_path):
    path = tmp_path / "a-guide.md"
    path.write_text(f"{HEADER}Text.\n\n```python\nprint(1)\n```\n", encoding="utf-8")
    assert 'class="mermaid"' not in parse_guide(path).body


def test_export_writes_the_diagram_back_as_a_fenced_block(tmp_path):
    body = guide_with(tmp_path, DIAGRAM).body
    markdown = html_to_markdown(body)
    assert f"```mermaid\n{DIAGRAM}\n```" in markdown


# check_guides rules

def test_a_complete_diagram_has_no_problems(tmp_path):
    assert guide_problems(guide_with(tmp_path, DIAGRAM)) == []


@pytest.mark.parametrize("diagram, message", [
    ("pie\n  accTitle: T\n  accDescr: D\n  \"a\": 1", "should start with one of"),
    ("flowchart LR\n  accDescr: D\n  A --> B", "needs a line starting with accTitle:"),
    ("flowchart LR\n  accTitle: T\n  A --> B", "needs a line starting with accDescr:"),
    ("flowchart LR\n  accTitle:\n  accDescr:\n  A --> B", "accTitle:"),
])
def test_diagram_problems_are_reported_in_plain_words(tmp_path, diagram, message):
    problems = guide_problems(guide_with(tmp_path, diagram))
    assert any("Diagram 1" in p and message in p for p in problems)


@pytest.mark.parametrize("first_line", ["graph TD", "flowchart TD", "sequenceDiagram", "stateDiagram-v2"])
def test_supported_diagram_kinds(first_line):
    html = f'<pre class="mermaid">{first_line}\naccTitle: T\naccDescr: D\n</pre>'
    assert diagram_problems(html) == []


def test_every_shipped_diagram_passes_the_rules():
    shipped = [parse_guide(path) for path in sorted(GUIDES_DIR.glob("*.md"))]
    assert sum(g.body.count('class="mermaid"') for g in shipped) >= 5
    assert [p for g in shipped for p in diagram_problems(g.body)] == []


# Browser

SECTIONS = "".join(f"<h2>Part {n}</h2><p>Text {n}.</p>" for n in range(2, 7))


@pytest.fixture
def browser_page(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")  # Playwright's sync API runs an event loop in the test thread
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as error:
            pytest.skip(f"No browser available for Playwright: {error}")
        yield browser.new_page()
        browser.close()


@pytest.mark.django_db(transaction=True)
def test_diagrams_draw_as_svg_without_errors(live_server, browser_page):
    user = make_user("proposer", "tech_risk")
    approver = make_user("approver", "tech_risk")
    shipped = parse_guide(GUIDES_DIR / "choosing-how-to-respond-to-a-risk.md")
    closed_card = f'<p>Intro.</p><h2>Part 1</h2><pre class="mermaid">{DIAGRAM}</pre>{SECTIONS}'
    first = make_page(user, approver, title=shipped.title, body=shipped.body)
    second = make_page(user, approver, title="Diagram in a closed card", body=closed_card)
    for page in (first, second):
        browser_page.goto(live_server.url + reverse("wiki:page", args=[page.slug]))
        browser_page.wait_for_selector("html[data-diagrams=ready]", timeout=30000)
        assert browser_page.locator("pre.mermaid svg").count() >= 1
        assert "Syntax error" not in browser_page.content()
        assert "mermaid version" not in browser_page.content()
        assert browser_page.locator("pre.mermaid:not([data-processed])").count() == 0
    # A card holding a diagram starts open; the other cards of a long guide stay closed
    assert browser_page.locator("details.section-card[open]").count() == 1
    assert browser_page.locator("details.section-card[open] pre.mermaid").count() == 1


@pytest.mark.django_db(transaction=True)
def test_a_page_without_a_diagram_does_not_load_mermaid(live_server, browser_page):
    user = make_user("proposer", "tech_risk")
    approver = make_user("approver", "tech_risk")
    page = make_page(user, approver, title="No diagram here")
    loaded = []
    browser_page.on("request", lambda request: loaded.append(request.url))
    browser_page.goto(live_server.url + reverse("wiki:page", args=[page.slug]))
    browser_page.wait_for_load_state("networkidle")
    assert not [url for url in loaded if "mermaid" in url]


@pytest.mark.django_db(transaction=True)
def test_clicking_a_stage_box_shows_that_stage_beside_the_diagram(live_server, browser_page):
    user = make_user("proposer", "tech_risk")
    approver = make_user("approver", "tech_risk")
    shipped = parse_guide(GUIDES_DIR / "initiative-lifecycle.md")
    page = make_page(user, approver, title=shipped.title, body=shipped.body)
    browser_page.set_viewport_size({"width": 1400, "height": 1000})
    browser_page.goto(live_server.url + reverse("wiki:page", args=[page.slug]))
    browser_page.wait_for_selector("html[data-diagrams=ready]", timeout=30000)
    assert browser_page.locator("pre.mermaid .diagram-link").count() == 7
    browser_page.locator("pre.mermaid .diagram-link", has_text="Stage 3").click()
    panel = browser_page.locator(".diagram-panel")
    assert panel.locator("h3").inner_text() == "Stage 3: Test and validate"
    assert "Migration rehearsal reconciled" in panel.inner_text()
    assert panel.locator("[id]").count() == 0
    assert browser_page.evaluate("location.hash") == ""
    # The diagram's own card is open; the stage cards below stay closed
    assert browser_page.locator("details.section-card[open]").count() == 1
    browser_page.screenshot(path="/tmp/lifecycle.png", full_page=False)
