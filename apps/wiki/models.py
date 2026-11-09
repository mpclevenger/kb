"""The database tables for guides, FAQ questions and visitor comments."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify

from apps.core.references import HELP as REFERENCES_HELP, check_references
from apps.core.versioning import GovernedEntity, GovernedVersion
from apps.platforms.models import Platform
from apps.topics.models import Topic


class Section(models.TextChoices):
    BUILD = "build", "Build your controls"
    RUN = "run", "Run your controls"
    BEST_PRACTICE = "best_practice", "Best practices"
    AUDIT_PREP = "audit_prep", "Audit prep"


class Page(GovernedEntity):
    slug = models.SlugField(max_length=120, unique=True)

    def __str__(self):
        version = self.current()
        return version.title if version else self.slug

    def get_absolute_url(self):
        return reverse("wiki:page", args=[self.slug])

    def get_list_url(self):
        return reverse("wiki:index")


class PageVersion(GovernedVersion):
    entity = models.ForeignKey(Page, on_delete=models.PROTECT, related_name="versions")
    title = models.CharField(max_length=160)
    section = models.CharField(max_length=20, choices=Section.choices)
    platform = models.ForeignKey(
        Platform, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="The platform this page is about, if any.",
    )
    body = models.TextField(blank=True)
    owner_role = models.CharField(
        max_length=120, help_text="The role accountable for this page, for example Tech Risk or Platform owner."
    )
    review_by = models.DateField(help_text="Date this page must be reviewed again.")
    references = models.JSONField(default=list, blank=True, help_text=REFERENCES_HELP)

    class Meta(GovernedVersion.Meta):
        pass

    def clean(self):
        super().clean()
        check_references(self.references)


# Page addresses that are already taken by other pages under /guides/.
RESERVED_SLUGS = frozenset({"faq", "audit-prep", "new", "edit"})


def unique_page_slug(title):
    base = slugify(title)[:110] or "page"
    slug, n = base, 2
    while slug in RESERVED_SLUGS or Page.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Faq(GovernedEntity):
    def __str__(self):
        version = self.current()
        return version.question if version else f"FAQ {self.pk}"

    def get_absolute_url(self):
        return reverse("wiki:faq_detail", args=[self.pk])

    def get_list_url(self):
        return reverse("wiki:faq")


class FaqVersion(GovernedVersion):
    entity = models.ForeignKey(Faq, on_delete=models.PROTECT, related_name="versions")
    question = models.CharField(max_length=200)
    answer = models.TextField(help_text="A short answer. Link to a guide or control for the detail.")
    topic = models.ForeignKey(
        Topic, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Leave empty for questions that apply everywhere.",
    )
    related_pages = models.ManyToManyField(Page, blank=True, related_name="+")

    class Meta(GovernedVersion.Meta):
        pass

    def copy_relations_from(self, base):
        self.related_pages.set(base.related_pages.all())


class FeedbackStatus(models.TextChoices):
    NEW = "new", "New"
    PLANNED = "planned", "Planned"
    DONE = "done", "Done"
    DECLINED = "declined", "Declined"


class Feedback(models.Model):
    """A comment left on a page by anyone who can read TRAC. Tech Risk replies; not versioned."""

    about_url = models.CharField(max_length=300, help_text="The page the comment was left on.")
    about_label = models.CharField(max_length=200)
    section = models.CharField(max_length=80, help_text="The part of the page the comment is about.")
    comment = models.TextField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=FeedbackStatus.choices, default=FeedbackStatus.NEW)
    response = models.TextField(blank=True, help_text="Shown to the person who left the comment.")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.about_label}: {self.section}"


def _lock_related_pages(sender, instance, action, **kwargs):
    if action.startswith("pre_") and isinstance(instance, FaqVersion) and instance.status != "draft":
        from apps.core.versioning import ImmutableVersionError

        raise ImmutableVersionError("Related pages can't change after the FAQ is submitted.")


models.signals.m2m_changed.connect(_lock_related_pages, sender=FaqVersion.related_pages.through)
