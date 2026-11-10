"""The database tables for topics, their ordered lifecycle stages, and their themes."""

from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

ICON_CHOICES = [
    ("key", "Key"),
    ("git-branch", "Branch"),
    ("file-search", "File search"),
    ("bug", "Bug"),
    ("cloud", "Cloud"),
    ("lifebuoy", "Lifebuoy"),
    ("building", "Building"),
    ("lock", "Lock"),
    ("checklist", "Checklist"),
    ("network", "Network"),
    ("clock", "Clock"),
]


class Topic(models.Model):
    """A subject area people browse by. Managed by Tech Risk."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    id_prefix = models.CharField(
        max_length=3,
        unique=True,
        validators=[RegexValidator(r"^[A-Z]{2,3}$", "Use 2 or 3 capital letters.")],
        help_text="Prefix for control IDs in this topic, for example AC.",
    )
    icon = models.CharField(max_length=20, choices=ICON_CHOICES)
    summary = models.TextField(blank=True, help_text="The short story shown at the top of the topic page.")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("topics:detail", args=[self.slug])


class Stage(models.Model):
    """One step in a topic's lifecycle, in order."""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=40)
    position = models.PositiveIntegerField()
    summary = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["topic", "position"]
        constraints = [
            models.UniqueConstraint(fields=["topic", "position"], name="stage_unique_position"),
            models.UniqueConstraint(fields=["topic", "name"], name="stage_unique_name"),
        ]

    def __str__(self):
        return f"{self.topic}: {self.name}"


class Theme(models.Model):
    """Something that applies throughout a topic rather than at one stage."""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="themes")
    name = models.CharField(max_length=60)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["topic", "position", "name"]
        constraints = [
            models.UniqueConstraint(fields=["topic", "name"], name="theme_unique_name"),
        ]

    def __str__(self):
        return f"{self.topic}: {self.name}"
