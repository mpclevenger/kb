"""Checks the editor allows exactly the formatting the site keeps."""

import re
from pathlib import Path

from apps.wiki.richtext import ALLOWED_TAGS

EDITOR_JS = Path(__file__).resolve().parents[3] / "static" / "js" / "trac-editor.js"


def test_editor_allows_exactly_the_tags_the_server_keeps():
    """CONTENT_TAGS in trac-editor.js must list the same tags as ALLOWED_TAGS, or the editor
    would offer formatting that is stripped on save (or strip formatting the page may keep)."""
    source = EDITOR_JS.read_text()
    listed = re.search(r'var CONTENT_TAGS = "([^"]*)"', source).group(1)
    assert set(listed.split(",")) == ALLOWED_TAGS
