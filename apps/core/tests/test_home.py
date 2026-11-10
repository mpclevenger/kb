"""The front page pitches Tech Risk and links each tool; the Library has its own address."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.core import home_files

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_topics")
    call_command("seed_platforms")


def test_front_page_has_the_pitch_and_a_card_per_tool(client, monkeypatch):
    monkeypatch.setenv("TRUST_URL", "https://trust.example/")
    monkeypatch.delenv("INITIATIVES_URL", raising=False)
    html = client.get("/").content.decode()
    assert "<h1" in html and "Tech Risk helps teams" in html
    assert html.count('class="home-tool"') == len(home_files.tools()) >= 4
    assert 'href="/guides/">Open the guides<' in html
    assert 'href="https://trust.example/">Open TRUST<' in html
    assert "Link coming soon" in html  # the initiative tracker's address isn't set in this test
    assert 'href="/tools/initiative-tracker/"' in html


def test_each_tool_has_an_about_page(client):
    for tool in home_files.tools():
        html = client.get(reverse("core:tool", args=[tool.slug])).content.decode()
        assert tool.summary in html
    assert client.get("/tools/no-such-tool/").status_code == 404


def test_library_has_its_own_address_and_the_old_one_redirects(client):
    assert reverse("core:library") == "/library/"
    response = client.get(reverse("platforms:index"))
    assert response.status_code == 302 and response["Location"] == "/library/"
    html = client.get("/library/").content.decode()
    assert '<a class="trac-wordmark" href="/">' in html
    assert '<a href="/library/" aria-current="page">Library</a>' in html


def test_the_shipped_home_files_are_valid():
    assert home_files.problems() == []


def test_a_bad_link_line_is_explained(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: Tech Risk\n---\nHello.\n")
    (tmp_path / "tools" / "x.md").write_text("---\ntitle: X\nsummary: S\nbutton: Go\nlink: ftp://x\n---\n")
    assert "the link must be" in home_files.problems(tmp_path)[0]


def test_home_reader_without_tech_risk_role_can_open_it(sso):
    from apps.core.tests.support import As

    assert As("reader", "ro").get("/").status_code == 200


def test_under_construction_shows_a_badge_and_a_banner(tmp_path, monkeypatch, client):
    import shutil

    folder = tmp_path / "home"
    shutil.copytree(home_files.FOLDER, folder)
    path = folder / "tools" / "trust.md"
    path.write_text(path.read_text().replace("under_construction: no", "under_construction: yes"))
    monkeypatch.setattr(home_files, "FOLDER", folder)
    assert "Under construction" in client.get("/").content.decode()
    assert "isn't officially launched yet" in client.get("/tools/trust/").content.decode()
    assert "isn't officially launched yet" not in client.get("/tools/guides/").content.decode()


def test_a_coming_soon_tool_says_so_and_its_button_is_off(client, monkeypatch):
    monkeypatch.setenv("SOX_SCHEDULE_URL", "https://schedule.example/")
    html = client.get("/").content.decode()
    assert '<span class="home-badge">Coming soon</span>' in html
    assert 'href="https://schedule.example/"' not in html
    page = client.get(reverse("core:tool", args=["sox-control-schedule"])).content.decode()
    assert "Coming soon." in page and 'href="https://schedule.example/"' not in page
