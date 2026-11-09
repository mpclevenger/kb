"""The sign-in, sign-out and "who am I" pages."""

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import permissions
from .forms import TechRiskSignInForm, VisitorNameForm
from .middleware import VISITOR_NAME_KEY


def login_view(request):
    """Open mode: add a name to your comments. sso mode: sign-in happens outside TRAC, so explain that."""
    if settings.AUTH_MODE != "open":
        return render(request, "accounts/login.html")
    form = VisitorNameForm(request.POST or None, initial={"name": request.session.get(VISITOR_NAME_KEY, "")})
    if request.method == "POST" and form.is_valid():
        request.session[VISITOR_NAME_KEY] = form.cleaned_data["name"]
        return redirect("/")
    return render(request, "accounts/sign_in.html", {"form": form})


class StaffLoginView(LoginView):
    """Open mode: the owner signs in with a password (Tech Risk accounts only)."""

    template_name = "accounts/staff_login.html"
    authentication_form = TechRiskSignInForm
    next_page = "/"

    def dispatch(self, request, *args, **kwargs):
        if settings.AUTH_MODE != "open":
            raise Http404
        return super().dispatch(request, *args, **kwargs)


@require_POST
def logout_view(request):
    """Signing out puts the browser back to a plain visitor on the next page."""
    logout(request)
    return redirect("/")


def whoami(request):
    return render(
        request,
        "accounts/whoami.html",
        {"roles_list": sorted(permissions.user_roles(request.user))},
    )
