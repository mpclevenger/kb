"""The plain YAML files that hold the guidance for each category and platform.

content/platforms/categories/<category>.yaml  holds the common practices for a category (Database, Identity...).
content/platforms/<platform>.yaml             holds only what is different for one platform.

`read_folder` checks every file and returns Django-ready data plus plain-word problems. `sync` writes drafts or
proposed changes, and `export` writes the site's published guidance back to files. Whether a site copy still
matches its file is decided by `apps.core.content_sync`, exactly as for guides and controls.
The file format is explained in content/README.md.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core import content_sync as cs
from apps.core import versioning as v
from apps.core.references import check_references

from .catalog_file import PLATFORMS_DIR, load_yaml
from .categories import Category
from .models import AspectQuestion, Guidance, GuidanceVersion, Platform

CATALOG_NAME = "catalog.yaml"

# The two kinds of file: which key names the subject, which key holds the aspect texts.
CATEGORY_FILE = {"subject": "category", "texts": "practices"}
PLATFORM_FILE = {"subject": "platform", "texts": "considerations"}


@dataclass
class Item:
    """One parsed file."""

    path: Path
    title: str  # for messages, for example "Database guidance"
    target: dict  # how the site finds this guidance: {"category": key} or {"platform": platform}
    intro: str
    lines: list  # [{"question": id, "text": str}] in question order
    references: list  # [{"label": str, "url": str}]
    digest: str  # fingerprint of what the file says, to tell whether it changed

    @property
    def content(self):
        return {"intro": self.intro, "lines": self.lines, "references": self.references}


@dataclass
class Report:
    items: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def read_folder(folder=None):
    folder = Path(folder or PLATFORMS_DIR)
    report = Report()
    questions = list(AspectQuestion.objects.order_by("position", "id"))
    files = [(p, CATEGORY_FILE) for p in sorted((folder / "categories").glob("*.yaml"))]
    files += [(p, PLATFORM_FILE) for p in sorted(folder.glob("*.yaml")) if p.name != CATALOG_NAME]
    seen = set()
    for path, kind in files:
        item, problems = _read_file(path, kind, questions)
        report.problems += problems
        if item is None:
            continue
        key = item.title
        if key in seen:
            report.problems.append(f"{path.name}: there is more than one file for {item.title}.")
            continue
        seen.add(key)
        report.items.append(item)
    return report


def _read_file(path, kind, questions):
    """(the parsed Item, []) for a good file, or (None, [plain-word problems])."""
    problems = []

    def problem(message):
        problems.append(f"{path.name}: {message}")

    data, error = load_yaml(path)
    if error:
        return None, [error]
    subject_key, texts_key = kind["subject"], kind["texts"]
    allowed = {subject_key, "intro", texts_key, "references"}
    if not isinstance(data, dict):
        return None, [f"{path.name}: expected '{subject_key}', 'intro', '{texts_key}' and 'references'."]
    for key in data.keys() - allowed:
        problem(f"'{key}' isn't a known field. Use {', '.join(sorted(allowed))}.")
    target, title = _subject(data.get(subject_key), subject_key, problem)
    intro = data.get("intro") or ""
    if not isinstance(intro, str):
        problem("'intro' should be plain text.")
        intro = ""
    texts = _texts(data.get(texts_key) or {}, texts_key, questions, problem)
    references = _references(data.get("references") or [], problem)
    if problems or target is None:
        return None, problems
    lines = [{"question": q.pk, "text": texts[q.label.lower()]} for q in questions if q.label.lower() in texts]
    intro = intro.strip()
    digest = hashlib.sha256(json.dumps(
        {"intro": intro, "lines": lines, "references": references}, sort_keys=True).encode()).hexdigest()
    return Item(path, title, target, intro, lines, references, digest), []


def _subject(value, subject_key, problem):
    """(how the site finds the guidance, its title), or (None, None) after reporting a problem."""
    if subject_key == "category":
        if value not in Category.values:
            problem(f"'category' is '{value}', which isn't a category. Use one of: {', '.join(Category.values)}.")
            return None, None
        return {"category": value}, f"{Category(value).label} guidance"
    platform = Platform.objects.filter(name=value).first() if isinstance(value, str) else None
    if platform is None:
        names = ", ".join(Platform.objects.values_list("name", flat=True)) or "none yet; run seed_platforms first"
        problem(f"'platform' is '{value}', which isn't a platform on this site. Platforms: {names}.")
        return None, None
    return {"platform": platform}, f"{platform.name} guidance"


def _texts(entries, texts_key, questions, problem):
    """{lowercase aspect label: text}, checking every label is a real aspect question."""
    known = {q.label.lower() for q in questions}
    if not isinstance(entries, dict):
        problem(f"'{texts_key}' should list the aspect labels (Access, Change...) each followed by its text.")
        return {}
    texts = {}
    for label, text in entries.items():
        key = str(label).strip().lower()
        if key not in known:
            problem(f"'{label}' under {texts_key} isn't an aspect label. Use: {', '.join(q.label for q in questions)}.")
        elif key in texts:
            problem(f"'{label}' is listed twice under {texts_key}.")
        elif not isinstance(text, str) or not text.strip():
            problem(f"'{label}' under {texts_key} has no text. Add some, or remove the heading.")
        else:
            texts[key] = text.strip()
    return texts


def _references(entries, problem):
    if not isinstance(entries, list) or not all(isinstance(r, dict) for r in entries):
        problem("'references' should be a list of label and link entries.")
        return []
    references = [{"label": r.get("label"), "url": r.get("link")} for r in entries]
    try:
        check_references(references)
    except ValidationError as error:
        problem(" ".join(error.messages))
        return []
    return references


# ---- sync ----

def _find(target):
    return Guidance.objects.filter(**target).first()


def _same_as_site(version, item):
    return (version.intro, version.lines, version.references) == (item.intro, item.lines, item.references)


def sync(report, user, say, publish=False, force=False, dry_run=False):
    """Bring the site in line with the files. Returns a list of cs.Outcome."""
    cs.ensure_can_publish(publish)
    outcomes = []
    with transaction.atomic():
        for item in report.items:
            outcome = _sync_item(item, user, publish, force, dry_run)
            outcomes.append(outcome)
            say(outcome.message)
    return outcomes


def _sync_item(item, user, publish, force, dry_run):
    entity = _find(item.target)
    published = entity.current() if entity else None
    matches = bool(published and published.kind != v.Kind.RETIRE and _same_as_site(published, item))
    decision = cs.decide(entity, item.title, item.digest, force=force, site_matches_file=matches,
                         export_command="export_platforms")
    if decision.kind == cs.IS_NEW:
        if dry_run:
            return cs.Outcome(cs.NEW, f"Would create a draft: {item.title}.")
        entity, version = v.create_entity(Guidance, GuidanceVersion, user, item.target, **item.content)
        cs.record(entity, version, item.digest)
        cs.finish(version, user, publish)
        return cs.Outcome(cs.NEW, f"Created a draft: {item.title}.")
    if decision.kind != cs.UPDATE:
        if decision.remember and not dry_run:
            cs.record(entity, published, item.digest)
        return cs.Outcome(decision.outcome, decision.message)
    if dry_run:
        return cs.Outcome(cs.UPDATED, f"Would propose a change: {item.title}.")
    version = v.propose_change(entity, user, f"Updated from content/platforms/{item.path.name}", **item.content)
    cs.record(entity, version, item.digest)
    cs.finish(version, user, publish)
    return cs.Outcome(cs.UPDATED, f"Proposed a change: {item.title}.")


# ---- export ----

class Folded(str):
    """Text written as a wrapped block (>), the way the intro is in the files."""


class _Dumper(yaml.SafeDumper):
    """Writes text with several lines as a block, so bullet lists stay readable, and indents lists."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


_Dumper.add_representer(str, lambda dumper, text: dumper.represent_scalar(
    "tag:yaml.org,2002:str", text, style="|" if "\n" in text else None))
_Dumper.add_representer(Folded, lambda dumper, text: dumper.represent_scalar("tag:yaml.org,2002:str", text, style=">"))


def _file_comments(path):
    """The comment lines at the top of an existing file, so they survive an export."""
    lines = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("#"):
                break
            lines.append(line)
    return "\n".join(lines) + "\n\n" if lines else ""


def _entry(version, subject_key, texts_key, subject_name, questions):
    line_map = version.line_map
    texts = {q.label: line_map[q.pk].strip() + "\n" for q in questions if q.pk in line_map}
    entry = {subject_key: subject_name, "intro": Folded(version.intro.strip() + "\n") if version.intro.strip() else "",
             texts_key: texts,
             "references": [{"label": r["label"], "link": r["url"]} for r in version.references]}
    return {key: value for key, value in entry.items() if value}


def export(folder, say):
    """Write each published guidance to its file and mark it in sync. Returns the paths written."""
    folder = Path(folder or PLATFORMS_DIR)
    questions = list(AspectQuestion.objects.order_by("position", "id"))
    written = []
    for guidance in Guidance.objects.select_related("platform").order_by("category", "platform__name"):
        version = guidance.current()
        if version is None or version.kind == v.Kind.RETIRE:
            continue
        if guidance.platform_id:
            kind, name = PLATFORM_FILE, guidance.platform.name
            path = folder / f"{guidance.platform.slug}.yaml"
        else:
            kind, name = CATEGORY_FILE, guidance.category
            path = folder / "categories" / f"{guidance.category}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = yaml.dump(_entry(version, kind["subject"], kind["texts"], name, questions), Dumper=_Dumper,
                         sort_keys=False, allow_unicode=True, width=100)
        path.write_text(_file_comments(path) + body, encoding="utf-8")
        # Fingerprint what a reader of the file will see, so the next sync says "unchanged".
        item, _ = _read_file(path, kind, questions)
        if item is not None:
            cs.record(guidance, version, item.digest)
        written.append(path)
        say(f"Wrote {path.relative_to(folder)}.")
    return written
