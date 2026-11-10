"""A small helper that gives every form field the site's standard look."""

from django import forms

# Widgets that Bootstrap styles as a tick box (RadioSelect is a Select subclass, so list it first).
CHECK_WIDGETS = (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)


class BootstrapFormMixin:
    """Bootstrap classes, help text wiring and error marking. Put it before the form base class.

    Forms need no "class" in their widgets. Widgets only carry extra attributes (rows, size, type=date).
    A form that adds fields after calling super().__init__ should call style_fields() again.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            if widget.is_hidden:
                continue
            if isinstance(widget, CHECK_WIDGETS):
                widget.attrs["class"] = "form-check-input"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"
            if field.help_text:
                widget.attrs["aria-describedby"] = f"id_{name}_help"

    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            for name in self.errors:
                if name in self.fields:
                    widget = self.fields[name].widget
                    widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()
                    widget.attrs["aria-invalid"] = "true"

