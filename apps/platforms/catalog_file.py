"""The platform catalog file, content/platforms/catalog.yaml: read it and check it.

The file lists the platforms and the risk-area questions (Access, Change, Logging...) that every
platform page answers. `seed_platforms` loads it into a new site and `check_platforms` checks it.
The format is explained in the comments at the top of the file.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings

from apps.topics.models import Topic

from .categories import CATEGORY_KEYS
from .models import Hosting

PLATFORMS_DIR = Path(settings.BASE_DIR) / "content" / "platforms"
CATALOG_FILE = PLATFORMS_DIR / "catalog.yaml"

PLATFORM_KEYS = {"name", "categories", "hosting", "runs_on", "docs"}
ASPECT_KEYS = {"topic", "label", "question"}
MAX_NAME, MAX_LABEL, MAX_QUESTION = 80, 40, 200  # the database column sizes


@dataclass
class Catalog:
    platforms: list = field(default_factory=list)  # dicts with name, categories, hosting, runs_on, docs
    aspects: list = field(default_factory=list)  # dicts with topic, label, question
    problems: list = field(default_factory=list)


def load_yaml(path):
    """The file's contents, or (None, a plain-words problem)."""
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8")), None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = f" near line {mark.line + 1}" if mark else ""
        return None, f"{Path(path).name}: the file isn't valid YAML{line}. Check the indentation and colons."
    except OSError:
        return None, f"{Path(path).name}: the file can't be read."


def read_catalog(path=CATALOG_FILE):
    catalog = Catalog()
    name = Path(path).name
    data, problem = load_yaml(path)
    if problem:
        catalog.problems.append(problem)
        return catalog
    if not isinstance(data, dict) or not isinstance(data.get("platforms"), list) or not isinstance(data.get("aspects"), list):
        catalog.problems.append(f"{name}: expected two lists, 'platforms' and 'aspects'.")
        return catalog
    for key in data.keys() - {"platforms", "aspects"}:
        catalog.problems.append(f"{name}: '{key}' isn't a known field. Use platforms and aspects.")
    _read_platforms(data["platforms"], catalog, name)
    _read_aspects(data["aspects"], catalog, name)
    return catalog


def _check_entry(entry, allowed, where, catalog):
    if not isinstance(entry, dict):
        catalog.problems.append(f"{where}: expected a name and other fields, one entry per item.")
        return False
    for key in entry.keys() - allowed:
        catalog.problems.append(f"{where}: '{key}' isn't a known field.")
    return True


def _read_platforms(entries, catalog, file_name):
    names = [e.get("name") for e in entries if isinstance(e, dict)]
    seen = set()
    for number, entry in enumerate(entries, start=1):
        where = f"{file_name}, platform {entry.get('name') or number if isinstance(entry, dict) else number}"
        if not _check_entry(entry, PLATFORM_KEYS, where, catalog):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
            catalog.problems.append(f"{where}: needs a name of {MAX_NAME} characters or fewer.")
            continue
        if name in seen:
            catalog.problems.append(f"{where}: the name is used twice.")
        seen.add(name)
        categories = entry.get("categories")
        valid = isinstance(categories, list) and categories and len(set(categories)) == len(categories) and set(categories) <= CATEGORY_KEYS
        if not valid:
            catalog.problems.append(
                f"{where}: 'categories' needs at least one of {', '.join(sorted(CATEGORY_KEYS))}, each at most once."
            )
        hosting = entry.get("hosting") or ""
        if hosting not in Hosting.values and hosting != "":
            catalog.problems.append(f"{where}: hosting '{hosting}' isn't allowed. Use one of: {', '.join(Hosting.values)}.")
        runs_on = entry.get("runs_on")
        if runs_on is not None and (runs_on not in names or runs_on == name):
            catalog.problems.append(f"{where}: runs_on '{runs_on}' isn't another platform in this file.")
        docs = entry.get("docs")
        if docs is not None and not (isinstance(docs, str) and docs.startswith(("http://", "https://"))):
            catalog.problems.append(f"{where}: 'docs' should be a web link starting with https://.")
        catalog.platforms.append({
            "name": name, "categories": categories if valid else [], "hosting": hosting,
            "runs_on": runs_on, "docs": docs,
        })


def _read_aspects(entries, catalog, file_name):
    prefixes = set(Topic.objects.values_list("id_prefix", flat=True))
    seen = set()
    for number, entry in enumerate(entries, start=1):
        where = f"{file_name}, aspect {entry.get('label') or number if isinstance(entry, dict) else number}"
        if not _check_entry(entry, ASPECT_KEYS, where, catalog):
            continue
        topic, label, question = entry.get("topic"), entry.get("label"), entry.get("question")
        if not all(isinstance(x, str) and x.strip() for x in (topic, label, question)):
            catalog.problems.append(f"{where}: needs a topic, a label and a question.")
            continue
        if len(label) > MAX_LABEL or len(question) > MAX_QUESTION:
            catalog.problems.append(f"{where}: the label can be {MAX_LABEL} characters and the question {MAX_QUESTION}.")
        if topic not in prefixes:
            known = ", ".join(sorted(prefixes)) or "none yet; run seed_topics first"
            catalog.problems.append(f"{where}: '{topic}' isn't a topic ID prefix on this site. Prefixes: {known}.")
        if (topic, label.lower()) in seen:
            catalog.problems.append(f"{where}: this topic already has a question with that label.")
        seen.add((topic, label.lower()))
        catalog.aspects.append({"topic": topic, "label": label, "question": question.strip()})
