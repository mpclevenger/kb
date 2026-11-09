"""Control levels: how important a control is, read from content/controls/levels.yaml.

The owner defines the levels there, most important first. This module is the one place that
reads and checks that file (once, then remembered) and answers the questions every page asks:
what are the levels, which order do they rank in, and is a level shown or folded away?
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings

LEVELS_FILE = Path(settings.BASE_DIR) / "content" / "controls" / "levels.yaml"
FILE_NAME = "levels.yaml"


class LevelsFileError(Exception):
    """The levels file is missing or wrong. The message says what to fix, in plain words."""


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    open: bool  # True: shown on pages. False: folded under "More controls".


def _parse(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LevelsFileError(f"{FILE_NAME} is missing. It lists the control levels (see content/controls/README.md).")
    except yaml.YAMLError:
        raise LevelsFileError(f"{FILE_NAME} isn't valid YAML. Check the indentation and colons.")
    entries = data.get("levels") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise LevelsFileError(f"{FILE_NAME}: expected a 'levels' list with at least one level.")
    levels, seen = [], set()
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or not str(entry.get("key") or "").strip():
            raise LevelsFileError(f"{FILE_NAME}: level number {number} needs a 'key'.")
        key = str(entry["key"]).strip()
        if not str(entry.get("label") or "").strip():
            raise LevelsFileError(f"{FILE_NAME}: level '{key}' needs a 'label'.")
        if key in seen:
            raise LevelsFileError(f"{FILE_NAME}: the key '{key}' is used twice.")
        if not isinstance(entry.get("open"), bool):
            raise LevelsFileError(f"{FILE_NAME}: level '{key}' needs 'open: true' or 'open: false'.")
        seen.add(key)
        levels.append(Level(key=key, label=str(entry["label"]).strip(), open=entry["open"]))
    return tuple(levels)


@lru_cache(maxsize=None)
def _cached(path):
    return _parse(path)


def clear_cache():
    """Forget what was read, so the file is read again (used after editing it, and in tests)."""
    _cached.cache_clear()


def all_levels():
    return _cached(str(LEVELS_FILE))


def problem():
    """A plain-words message if the levels file is wrong, otherwise None (used by check_controls)."""
    try:
        all_levels()
    except LevelsFileError as error:
        return str(error)
    return None


def keys():
    return [level.key for level in all_levels()]


def choices():
    """(key, label) pairs for the control form's Level dropdown."""
    return [(level.key, level.label) for level in all_levels()]


def first_key():
    """The most important level."""
    return all_levels()[0].key


def default_key():
    """The level a new control starts at: the first one that is not shown by default (else the last)."""
    for level in all_levels():
        if not level.open:
            return level.key
    return all_levels()[-1].key


def _find(key):
    return next((level for level in all_levels() if level.key == key), None)


def label(key):
    level = _find(key)
    return level.label if level else key


def is_open(key):
    """Shown on pages? A level that is no longer in the file counts as folded."""
    level = _find(key)
    return bool(level and level.open)


def position(key):
    """Rank of a level (0 is the most important). Unknown levels rank last."""
    return keys().index(key) if key in keys() else len(all_levels())
