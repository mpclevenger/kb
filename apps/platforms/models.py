"""Technology catalog: platforms and the risk-aspect questions every platform page answers.
Managed by Tech Risk like topics; narrative content for a platform lives in governed wiki pages
tagged with the platform."""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import NoReverseMatch, reverse
from django.utils.text import slugify

from apps.core.references import HELP as REFERENCES_HELP, check_references
from apps.core.versioning import GovernedEntity, GovernedVersion
from apps.topics.models import Topic

from .categories import CATEGORY_KEYS, Category


class Hosting(models.TextChoices):
    CLOUD = "cloud", "Cloud"
    ON_PREM = "on_prem", "On-premises"
    SAAS = "saas", "Software as a service"
    HYBRID = "hybrid", "Hybrid"


class Platform(models.Model):
    name = models.CharField(
        max_length=80, unique=True, error_messages={"unique": "A platform with this name already exists."}
    )
    slug = models.SlugField(max_length=90, unique=True)
    categories = models.JSONField(
        default=list, help_text="The categories this platform belongs to. The first one sets its color."
    )
    hosting = models.CharField(max_length=10, choices=Hosting.choices, blank=True)
    runs_on = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="The platform this one runs on, for example SQL Server runs on Windows Server.",
    )
    owner = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=240, blank=True)
    doc_links = models.JSONField(
        default=list, blank=True, help_text='Links to documentation: [{"label": str, "url": str}].'
    )
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "name"]

    @property
    def primary_category(self):
        return self.categories[0]

    def clean(self):
        super().clean()
        valid = (
            isinstance(self.categories, list)
            and self.categories
            and all(isinstance(key, str) for key in self.categories)
            and set(self.categories) <= CATEGORY_KEYS
            and len(set(self.categories)) == len(self.categories)
        )
        if not valid:
            raise ValidationError({"categories": "Pick at least one category from the list, each at most once."})
        if self.runs_on_id and self.runs_on_id == self.pk:
            raise ValidationError({"runs_on": "A platform can't run on itself."})
        check_references(self.doc_links, field="doc_links")

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug, n = base, 2
            while Platform.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """The platform's main category page with this platform's specifics switched on."""
        return self.url_in(self.primary_category) if self.categories else ""

    def url_in(self, category):
        """A category page with this platform's specifics switched on."""
        try:
            return f"{reverse('platforms:category', args=[category])}?platform={self.slug}"
        except NoReverseMatch:
            return ""


class AspectQuestion(models.Model):
    """A plain technical question every platform page answers for one topic."""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="aspect_questions")
    label = models.CharField(max_length=40, help_text="Short name shown in the checklist, for example Access.")
    text = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.text


class Guidance(GovernedEntity):
    """What good looks like for a category or for one platform, one line per aspect question."""

    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, null=True, blank=True, related_name="+")

    class Meta:
        verbose_name_plural = "guidance"
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(category="") & models.Q(platform__isnull=False))
                | (~models.Q(category="") & models.Q(platform__isnull=True)),
                name="guidance_category_or_platform",
            ),
            models.UniqueConstraint(
                fields=["category"], condition=~models.Q(category=""), name="guidance_unique_category"
            ),
            models.UniqueConstraint(
                fields=["platform"], condition=models.Q(platform__isnull=False), name="guidance_unique_platform"
            ),
        ]

    def __str__(self):
        return f"Guidance for {self.platform.name if self.platform_id else self.get_category_display()}"

    def get_absolute_url(self):
        if self.platform_id:
            return self.platform.get_absolute_url()
        return reverse("platforms:category", args=[self.category])


class GuidanceVersion(GovernedVersion):
    entity = models.ForeignKey(Guidance, on_delete=models.PROTECT, related_name="versions")
    intro = models.TextField(blank=True, help_text="A short introduction shown at the top of the page.")
    lines = models.JSONField(
        default=list, blank=True, help_text='One line per aspect question: [{"question": id, "text": str}].'
    )
    references = models.JSONField(default=list, blank=True, help_text=REFERENCES_HELP)

    class Meta(GovernedVersion.Meta):
        pass

    @property
    def line_map(self):
        """Guidance text by aspect question id."""
        return {line["question"]: line["text"] for line in self.lines}

    def clean(self):
        super().clean()
        valid = isinstance(self.lines, list) and all(
            isinstance(line, dict)
            and isinstance(line.get("question"), int)
            and isinstance(line.get("text"), str)
            and line["text"].strip()
            for line in self.lines
        )
        if not valid:
            raise ValidationError({"lines": "Each line needs a question and some text."})
        ids = [line["question"] for line in self.lines]
        if len(set(ids)) != len(ids) or AspectQuestion.objects.filter(pk__in=ids).count() != len(ids):
            raise ValidationError({"lines": "Use each existing question at most once."})
        check_references(self.references)
