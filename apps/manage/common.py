"""Pieces shared by the Manage pages. Every save is logged as a CatalogChange."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import can_admin, permission_required_for
from apps.platforms.models import Platform
from apps.topics.models import Topic

from .models import CatalogChange, snapshot

Action = CatalogChange.Action
admin_only = permission_required_for(can_admin)


def save_form(request, form):
    """Save a valid form and log it. Returns False when an edit changed nothing."""
    obj = form.instance
    creating = obj.pk is None
    if not creating and not form.has_changed():
        return False
    fields = form._meta.fields
    with transaction.atomic():
        before = {} if creating else snapshot(type(obj).objects.get(pk=obj.pk), fields)
        obj = form.save()
        CatalogChange.record(
            request.user, obj, Action.CREATE if creating else Action.UPDATE, before, snapshot(obj, fields)
        )
    return True


def edit_page(request, form_class, template, url_name, instance=None, **context):
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        changed = save_form(request, form)
        if changed:
            messages.success(request, f"Saved {form.instance._meta.verbose_name}: {form.instance}.")
        else:
            messages.info(request, "Nothing was changed.")
        return redirect(url_name, pk=form.instance.pk)
    noun = form.instance._meta.verbose_name
    context.update(form=form, object=instance, noun=noun, heading=str(instance) if instance else f"New {noun}")
    if instance:
        context["history"] = CatalogChange.for_object(instance).select_related("actor")
    return render(request, template, context)


# One view for both Topic and Platform: they are switched on and off the same way, never deleted.
@admin_only
@require_POST
def set_active(request, model_name, pk):
    obj = get_object_or_404({"topic": Topic, "platform": Platform}[model_name], pk=pk)
    active = request.POST.get("active") == "true"
    if obj.is_active != active:
        with transaction.atomic():
            obj.is_active = active
            obj.save(update_fields=["is_active"])
            CatalogChange.record(
                request.user,
                obj,
                Action.REACTIVATE if active else Action.DEACTIVATE,
                {"is_active": not active},
                {"is_active": active},
            )
        messages.success(request, f"{'Reactivated' if active else 'Deactivated'} {obj}.")
    return redirect(f"manage:{model_name}_edit", pk=pk)
