"""The code behind the Submit, Approve, Reject and Withdraw buttons: each moves a draft one step along."""

from datetime import date, datetime, time

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.permissions import can_see_version

from . import versioning as v


def _load_version(request, type_id, version_id):
    if not request.user.is_authenticated:
        raise PermissionDenied
    content_type = get_object_or_404(ContentType, pk=type_id)
    model = content_type.model_class()
    if model is None or not issubclass(model, v.GovernedVersion):
        raise Http404
    version = get_object_or_404(model.objects.select_related("entity"), pk=version_id)
    if not can_see_version(request.user, version):
        raise Http404
    return version


def _safe_next(request):
    target = request.POST.get("next", "")
    if not target.startswith("/") or target.startswith("//"):
        return None
    allowed = url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return target if allowed else None


def _entity_url(entity, version=None):
    getter = getattr(entity, "get_absolute_url", None)
    if getter is None:
        return None
    url = getter()
    if version is not None and version.status != v.Status.PUBLISHED:
        url = f"{url}?version={version.number}"
    return url


def _redirect_after(request, entity, version, discarded=False):
    if discarded:
        if entity.pk is None:
            list_url = getattr(entity, "get_list_url", None)
            return redirect(list_url() if list_url else reverse("core:home"))
        return redirect(_entity_url(entity) or _safe_next(request) or reverse("core:home"))
    return redirect(_safe_next(request) or _entity_url(entity, version) or reverse("core:home"))


def _effective_from(raw):
    """Start of the chosen day in the site time zone; None means publish now."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        raise ValidationError("Enter the start date as year-month-day.")
    today = timezone.localdate()
    if day < today:
        raise ValidationError("The start date can't be in the past.")
    if day == today:
        return None
    return timezone.make_aware(datetime.combine(day, time.min))


def _submit(request, version):
    v.submit(version, request.user)
    return "Submitted for review"


def _withdraw(request, version):
    v.withdraw(version, request.user)
    return "Withdrawn"


def _approve(request, version):
    effective_from = _effective_from(request.POST.get("effective_date"))
    v.approve_and_publish(
        version, request.user, request.POST.get("comment", "").strip(), effective_from
    )
    return "Approved and published"


def _reject(request, version):
    v.reject(version, request.user, request.POST.get("comment", ""))
    return "Rejected"


ACTIONS = {
    "submit": _submit,
    "withdraw": _withdraw,
    "approve": _approve,
    "reject": _reject,
}


def _run(request, type_id, version_id, action):
    version = _load_version(request, type_id, version_id)
    entity = version.entity
    try:
        message = ACTIONS[action](request, version)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, message)
    version.refresh_from_db()
    return _redirect_after(request, entity, version)


def make_view(action):
    @require_POST
    def view(request, type_id, version_id):
        return _run(request, type_id, version_id, action)

    view.__name__ = f"{action}_view"
    return view


submit_view = make_view("submit")
withdraw_view = make_view("withdraw")
approve_view = make_view("approve")
reject_view = make_view("reject")


@require_POST
def discard_view(request, type_id, version_id):
    version = _load_version(request, type_id, version_id)
    entity = version.entity
    try:
        v.discard_draft(version, request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return _redirect_after(request, entity, version)
    messages.success(request, "Draft discarded")
    return _redirect_after(request, entity, version, discarded=True)
