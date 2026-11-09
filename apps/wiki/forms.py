"""Create and edit forms for wiki pages and FAQ questions."""

from django import forms

from apps.core.versioning import effective_entities
from apps.platforms.models import Platform
from apps.rcm.forms import EditForm, GovernedForm, platform_choices, textarea_widget
from apps.topics.models import Topic

from .models import FaqVersion, Page, PageVersion, Section
from .richtext import RichTextField

STARTER_HEADINGS = {
    Section.BUILD: ["When to use this", "How to design it", "What good looks like"],
    Section.RUN: ["Before you start", "Steps", "Checks before you finish"],
}


def starter_body(section):
    """Empty section headings for a new page in this section; best practices and audit prep start blank."""
    return "".join(f"<h2>{heading}</h2>" for heading in STARTER_HEADINGS.get(section, []))


class PageForm(GovernedForm):
    version_model = PageVersion

    section = forms.ChoiceField(
        choices=[("", "Select")] + Section.choices,
        label="Section",
        help_text="Build and Run are about controls. Best practices cover a technology or area. Audit prep is about audits.",
    )
    platform = forms.ModelChoiceField(
        queryset=Platform.objects.none(),
        required=False,
        label="Platform",
        empty_label="No specific platform",
        help_text="Pick a platform if the page is about one.",
    )
    body = RichTextField(
        required=False,
        label="Page content",
        help_text="Use headings to split the page into sections. A new Build or Run page with no content starts with an outline.",
    )

    field_order = [
        "section", "title", "platform", "body", "owner_role", "review_by", "references", "change_summary",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = Platform.objects.filter(is_active=True)
        field = self.fields["platform"]
        field.queryset = active
        field.widget.choices = [("", field.empty_label)] + platform_choices(active)


class FaqForm(EditForm):
    version_model = FaqVersion

    question = forms.CharField(max_length=200, label="Question")
    answer = forms.CharField(
        label="Answer",
        help_text=FaqVersion._meta.get_field("answer").help_text,
        widget=textarea_widget(rows=5),
    )
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.filter(is_active=True),
        required=False,
        label="Topic",
        empty_label="General (applies everywhere)",
    )
    related_pages = forms.ModelMultipleChoiceField(
        queryset=Page.objects.none(),
        required=False,
        label="Related pages",
        help_text="Hold Ctrl or Cmd to pick more than one.",
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    change_summary = forms.CharField(
        label="What are you changing, and why?",
        max_length=500,
        help_text="One or two sentences for the reviewer.",
        widget=textarea_widget(rows=2),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pages = effective_entities(Page)
        field = self.fields["related_pages"]
        field.queryset = pages
        field.label_from_instance = str

    def content_keys(self):
        return [n for n in self.fields if n not in ("change_summary", "related_pages")]

    def candidate_values(self, data):
        return {n: data[n] for n in self.content_keys() if n in data}
