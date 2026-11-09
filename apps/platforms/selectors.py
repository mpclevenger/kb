"""Platform and category pages: guidance lines and the control patterns that answer each aspect question."""

from dataclasses import dataclass, field

from django.db.models import prefetch_related_objects

from apps.rcm.selectors import fold_pairs

from .models import AspectQuestion, Guidance, Platform


def category_platforms(category):
    return Platform.objects.filter(categories__contains=[category], is_active=True)


def applicable_controls(controls, categories=(), platforms=()):
    """The (control, version) pairs from `controls` tagged with one of the categories or platforms."""
    platform_ids = {platform.pk for platform in platforms}
    prefetch_related_objects([version for _, version in controls], "platforms")  # no-op once fetched
    return [
        (control, version)
        for control, version in controls
        if set(categories).intersection(version.categories or [])
        or any(p.pk in platform_ids for p in version.platforms.all())
    ]


def current_guidance(**target):
    """The published guidance version for `category=<key>` or `platform=<Platform>`, or None."""
    guidance = Guidance.objects.filter(**target).first()
    return guidance.current() if guidance else None


def active_questions():
    return list(AspectQuestion.objects.select_related("topic").filter(topic__is_active=True))


@dataclass
class AspectRow:
    question: AspectQuestion
    line: str = ""
    controls: list = field(default_factory=list)  # controls at open levels, most important first
    more: list = field(default_factory=list)  # LevelGroups folded under "More controls"

    @property
    def has_content(self):
        return bool(self.line or self.controls or self.more)


def aspect_rows(controls, questions, guidance=None):
    """One row per aspect question: the guidance line and the controls on the same topic.

    `questions` is active_questions(); pass the same list to every call on a page.
    """
    lines = guidance.line_map if guidance else {}
    rows = []
    for question in questions:
        shown, more = fold_pairs([(c, v) for c, v in controls if v.topic_id == question.topic_id])
        rows.append(AspectRow(question=question, line=lines.get(question.pk, ""), controls=shown, more=more))
    return rows
