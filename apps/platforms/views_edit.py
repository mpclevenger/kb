"""Tech Risk edits the guidance for a category or a platform. Every save lands as a draft."""

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.permissions import can_propose, permission_required_for
from apps.core import versioning as v

from .categories import CATEGORY_KEYS, Category
from .forms import GuidanceForm
from .models import Guidance, GuidanceVersion, Platform
from .selectors import active_questions

SAVED = "Draft saved. Check it over, then submit it for review when you're ready."


def _blocked_message(user, open_version):
    if open_version.proposed_by_id == user.pk:
        return "Your change is in review. Withdraw it if you want to edit it again."
    return (
        f"Someone else is already working on a change (version {open_version.number}, "
        f"{open_version.get_status_display().lower()}). Changes go one at a time."
    )


def _save(user, form, target, entity, draft):
    content = form.content()
    summary = {"change_summary": form.cleaned_data["change_summary"]} if "change_summary" in form.fields else {}
    with transaction.atomic():
        if entity is None:
            return v.create_entity(Guidance, GuidanceVersion, user, target, **content)
        if draft is not None:
            return entity, v.update_draft(draft, user, **content, **summary)
        return entity, v.propose_change(entity, user, **content, **summary)


def _edit(request, target, name, cancel_url):
    user = request.user
    entity = Guidance.objects.filter(**target).first()
    open_version = entity.open_proposal() if entity else None
    draft = open_version if (
        open_version and open_version.status == v.Status.DRAFT and open_version.proposed_by_id == user.pk
    ) else None
    context = {
        "nav_active": "library",
        "name": name,
        "cancel_url": cancel_url,
        "version": open_version,
    }
    if open_version is not None and draft is None:
        context["blocked"] = _blocked_message(user, open_version)
        context["proposed"] = [
            (q, open_version.line_map[q.pk]) for q in active_questions() if q.pk in open_version.line_map
        ]
        return render(request, "platforms/guidance_form.html", context)

    source = draft or (entity and (entity.current() or entity.versions.order_by("-number").first()))
    kwargs = {"with_summary": entity is not None and (draft is None or draft.number > 1)}
    if request.method == "POST":
        form = GuidanceForm(request.POST, **kwargs)
        if form.is_valid():
            _save(user, form, target, entity, draft)
            messages.success(request, SAVED)
            return redirect(request.get_full_path())
    else:
        form = GuidanceForm(initial=GuidanceForm.initial_from(source) if source else None, **kwargs)
    return render(request, "platforms/guidance_form.html", {**context, "form": form})


@permission_required_for(can_propose)
def guidance_edit(request, key=None, slug=None):
    """Edit guidance for a category (`key`) or for a platform (`slug`)."""
    if key is not None:
        if key not in CATEGORY_KEYS:
            raise Http404
        return _edit(request, {"category": key}, Category(key).label, reverse("platforms:category", args=[key]))
    platform = get_object_or_404(Platform, slug=slug, is_active=True)
    return _edit(request, {"platform": platform}, platform.name, platform.get_absolute_url())
