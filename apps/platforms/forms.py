"""The form Tech Risk uses to write the guidance for a category or platform."""

from django import forms

from apps.rcm.forms import CHANGE_SUMMARY, EditForm, ReferencesField, textarea_widget

from .models import GuidanceVersion
from .selectors import active_questions

LINE_PREFIX = "line_"


class GuidanceForm(EditForm):
    """An introduction, one line per aspect question, and references."""

    version_model = GuidanceVersion

    intro = forms.CharField(
        required=False,
        label="Introduction",
        help_text="Two or three sentences at the top of the page.",
        widget=textarea_widget(3),
    )
    references = ReferencesField(label="References")
    change_summary = CHANGE_SUMMARY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_names = []
        for question in active_questions():
            name = f"{LINE_PREFIX}{question.pk}"
            self.fields[name] = forms.CharField(
                required=False, label=question.label, help_text=question.text, widget=textarea_widget(2)
            )
            self.line_names.append(name)
        self.style_fields()  # for the fields just added
        self.order_fields(["intro", *self.line_names, "references", "change_summary"])

    def line_fields(self):
        return [self[name] for name in self.line_names]

    def lines(self):
        """Cleaned lines as stored: [{"question": id, "text": str}], skipping blanks."""
        lines = [(int(name[len(LINE_PREFIX):]), self.cleaned_data.get(name, "").strip()) for name in self.line_names]
        return [{"question": question, "text": text} for question, text in lines if text]

    def content(self):
        return {"intro": self.cleaned_data["intro"].strip(), "lines": self.lines(), "references": self.cleaned_data["references"]}

    def candidate_values(self, data):
        return self.content()

    @staticmethod
    def initial_from(version):
        initial = {"intro": version.intro, "references": version.references}
        initial.update({f"{LINE_PREFIX}{question}": text for question, text in version.line_map.items()})
        return initial
