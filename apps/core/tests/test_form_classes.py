"""Checks that every form field gets the site's standard look and errors are marked."""

import pytest
from django import forms

from apps.platforms.forms import GuidanceForm
from apps.rcm.forms import ControlForm, EvidenceRuleForm, RiskForm
from apps.wiki.forms import FaqForm, PageForm

FORMS = [ControlForm, RiskForm, EvidenceRuleForm, PageForm, FaqForm, GuidanceForm]


@pytest.mark.django_db
@pytest.mark.parametrize("form_class", FORMS, ids=lambda f: f.__name__)
def test_every_visible_field_gets_its_bootstrap_class(form_class):
    form = form_class()
    for name, field in form.fields.items():
        widget = field.widget
        if widget.is_hidden:
            continue
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
            expected = "form-check-input"
        elif isinstance(widget, forms.Select):
            expected = "form-select"
        else:
            expected = "form-control"
        assert widget.attrs.get("class") == expected, name


@pytest.mark.django_db
def test_invalid_fields_are_marked():
    form = FaqForm(data={})
    assert not form.is_valid()
    attrs = form.fields["question"].widget.attrs
    assert "is-invalid" in attrs["class"] and attrs["aria-invalid"] == "true"
