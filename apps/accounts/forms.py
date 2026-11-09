"""The two sign-in forms: a visitor adding their name, and Tech Risk signing in with a password."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.text import slugify

from apps.core.forms import BootstrapFormMixin

from . import permissions


class VisitorNameForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(label="Your name", max_length=40, required=False)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if name and not slugify(name):
            raise forms.ValidationError("Use letters or numbers in the name.")
        return name


class TechRiskSignInForm(BootstrapFormMixin, AuthenticationForm):
    """Django's username and password form, limited to Tech Risk accounts."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not permissions.is_tech_risk(user):
            raise forms.ValidationError("This account can't sign in here. Only Tech Risk accounts can.")
