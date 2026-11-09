"""Retire any governed item (guide, FAQ, control, risk, driver, evidence rule).

Retiring is a change like any other: it needs a reason and a second Tech Risk approver.
Once approved, the item drops out of lists, and its page stays reachable with a Retired notice.
"""

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.permissions import can_propose, permission_required_for

from . import versioning as v
from .workflow import _entity_url


def retire_url(entity):
    """Link to the Retire form, or None if the item can't be retired right now."""
    if entity.open_proposal() is not None or entity.is_retired():
        return None
    type_id = ContentType.objects.get_for_model(entity).pk
    return reverse("workflow:retire", args=[type_id, entity.pk])


def _load_entity(type_id, entity_id):
    model = get_object_or_404(ContentType, pk=type_id).model_class()
    if model is None or not issubclass(model, v.GovernedEntity):
        raise Http404
    return get_object_or_404(model, pk=entity_id)


@permission_required_for(can_propose)
def retire_view(request, type_id, entity_id):
    entity = _load_entity(type_id, entity_id)
    cancel_url = _entity_url(entity) or reverse("core:home")
    reason, error = "", None
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        try:
            with transaction.atomic():
                version = v.propose_retirement(entity, request.user, reason)
                v.submit(version, request.user)
        except ValidationError as problem:
            error = " ".join(problem.messages)
        else:
            messages.success(request, "Retirement sent for approval. Another member of Tech Risk needs to approve it.")
            return redirect(_entity_url(entity, version) or cancel_url)
    context = {"heading": f"Retire {entity}", "entity": entity, "reason": reason, "error": error, "cancel_url": cancel_url}
    return render(request, "core/retire.html", context)
