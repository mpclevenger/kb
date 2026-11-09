"""Checks the PowerShell helper at the top of the project: every verb it lists has code behind it."""

import re
from pathlib import Path

from django.conf import settings

SCRIPT = (Path(settings.BASE_DIR) / "trac.ps1").read_text(encoding="utf-8")
LISTED = re.findall(r"^    (\w+)\s+= \"", SCRIPT, flags=re.MULTILINE)
BRANCHES = re.findall(r"^        \"(\w+)\" \{", SCRIPT, flags=re.MULTILINE)
EXPECTED = ["setup", "run", "test", "check", "sync", "export", "demo", "help"]


def test_the_help_lists_every_verb_the_owner_was_promised():
    assert LISTED == EXPECTED


def test_every_listed_verb_has_a_matching_branch_and_the_other_way_round():
    assert sorted(LISTED) == sorted(BRANCHES)


def test_the_script_explains_blocked_scripts_and_checks_each_step():
    assert "powershell -ExecutionPolicy Bypass -File .\\trac.ps1 <verb>" in SCRIPT
    assert "$LASTEXITCODE -ne 0" in SCRIPT


def test_braces_and_quotes_balance():
    code = re.sub(r"#[^\n]*", "", SCRIPT)  # a rough guard against a typo; not a PowerShell parser
    assert code.count("{") == code.count("}") and code.count("(") == code.count(")")


def test_publish_is_only_passed_when_asked_and_demo_needs_demo_in_the_name():
    assert 'if ($Publish) { $arguments += "--publish" }' in SCRIPT
    assert "-notlike \"*demo*\"" in SCRIPT
