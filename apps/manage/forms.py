"""The forms Tech Risk uses to edit topics, platforms and aspect questions."""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.platforms.categories import Category
from apps.platforms.models import AspectQuestion, Platform
from apps.rcm.forms import ReferencesField
from apps.rcm.models import IdSequence
from apps.topics.models import Topic

PREFIX_LOCKED_HELP = (
    "Locked: controls or risks already use this prefix, and IDs are never renamed or reused."
)


def prefix_in_use(topic):
    return IdSequence.objects.filter(key__in=[topic.id_prefix, f"R-{topic.id_prefix}"]).exists()


class TopicForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Topic
        fields = ["name", "id_prefix", "icon", "summary", "position", "is_active"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 4})}
        labels = {"id_prefix": "ID prefix", "is_active": "Active"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and prefix_in_use(self.instance):
            self.fields["id_prefix"].disabled = True
            self.fields["id_prefix"].help_text = PREFIX_LOCKED_HELP


class PlatformForm(BootstrapFormMixin, forms.ModelForm):
    categories = forms.MultipleChoiceField(
        choices=Category.choices,
        label="Categories",
        help_text=Platform._meta.get_field("categories").help_text,
        widget=forms.CheckboxSelectMultiple,
    )
    doc_links = ReferencesField(label="Documentation links")

    class Meta:
        model = Platform
        fields = [
            "name", "categories", "hosting", "runs_on", "owner", "summary", "doc_links", "position", "is_active",
        ]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2})}
        labels = {"is_active": "Active"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["runs_on"].queryset = Platform.objects.filter(is_active=True)


class AspectQuestionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AspectQuestion
        fields = ["topic", "label", "text", "position"]
        widgets = {"text": forms.Textarea(attrs={"rows": 2})}
