"""Topic pages: the topic itself and its ordered stages and themes."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.topics.models import Stage, Theme, Topic

from .common import Action, admin_only, edit_page
from .forms import TopicForm
from .models import CatalogChange

# Ordered lists on the topic page. URL kind (also the related name on Topic): model, singular label, section title.
ITEM_KINDS = {
    "stages": (Stage, "stage", "Stages"),
    "themes": (Theme, "theme", "Themes"),
}


@admin_only
def topic_edit(request, pk=None):
    topic = get_object_or_404(Topic, pk=pk) if pk else None
    context = {}
    if topic:
        context["item_lists"] = [
            {
                "kind": kind,
                "title": title,
                "noun": noun,
                "items": getattr(topic, kind).all(),
                "max_length": model._meta.get_field("name").max_length,
                "summary_max_length": model._meta.get_field("summary").max_length if kind == "stages" else None,
            }
            for kind, (model, noun, title) in ITEM_KINDS.items()
        ]
    return edit_page(request, TopicForm, "manage/topic_form.html", "manage:topic_edit", topic, **context)


def renumber(items):
    """Give items contiguous positions 1..n in the order given.

    Stage positions are unique within a topic, so the rows are first moved above every target position.
    """
    if not items:
        return
    model = type(items[0])
    offset = max(item.position for item in items) + len(items)
    model.objects.filter(pk__in=[item.pk for item in items]).update(position=F("position") + offset)
    for number, item in enumerate(items, start=1):
        model.objects.filter(pk=item.pk).update(position=number)


def clean_item_name(model, items, name, exclude=None):
    name = name.strip()
    if not name:
        raise ValidationError("Enter a name.")
    max_length = model._meta.get_field("name").max_length
    if len(name) > max_length:
        raise ValidationError(f"Use {max_length} characters or fewer.")
    if items.filter(name__iexact=name).exclude(pk=exclude).exists():
        raise ValidationError(f"There is already one called \"{name}\".")
    return name


def save_item(model, noun, items, item, post):
    """Save a renamed item and, for stages, an edited summary. Returns the success message."""
    old_name, old_summary = item.name, getattr(item, "summary", "")
    item.name = clean_item_name(model, items, post.get("name", ""), exclude=item.pk)
    fields = ["name"]
    if hasattr(item, "summary"):
        item.summary = clean_item_summary(model, post.get("summary", ""))
        fields.append("summary")
    if item.name == old_name and getattr(item, "summary", "") == old_summary:
        return "Nothing was changed."
    item.save(update_fields=fields)
    if item.name != old_name:
        return f"Renamed {noun} \"{old_name}\" to \"{item.name}\"."
    return f"Updated the summary of {noun} \"{item.name}\"."


def clean_item_summary(model, summary):
    summary = summary.strip()
    max_length = model._meta.get_field("summary").max_length
    if len(summary) > max_length:
        raise ValidationError(f"Use {max_length} characters or fewer for the summary.")
    return summary


def apply_item_action(model, noun, topic, items, post):
    """Apply one add, rename, move or remove to a topic's ordered list. Returns the success message."""
    action = post.get("action")
    if action == "add":
        name = clean_item_name(model, items, post.get("name", ""))
        model.objects.create(topic=topic, name=name, position=len(items) + 1)
        return f"Added {noun} \"{name}\"."
    item = get_object_or_404(items, pk=post.get("item"))
    order = list(items)
    index = order.index(item)
    if action == "save":
        return save_item(model, noun, items, item, post)
    if action in ("up", "down"):
        target = index - 1 if action == "up" else index + 1
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            renumber(order)
        return f"Moved {noun} \"{item.name}\" {action}."
    if action == "remove":
        try:
            item.delete()
        except ProtectedError as error:
            raise ValidationError(
                f"Can't remove the {noun} \"{item.name}\": {len(error.protected_objects)} control, risk or page "
                "versions use it. Published versions can't be changed, so keep it or rename it instead."
            ) from error
        order.pop(index)
        renumber(order)
        return f"Removed {noun} \"{item.name}\"."
    raise Http404


def describe_items(kind, items):
    """Names, and stage summaries, as the text shown in the change log."""
    current = list(items.all())
    described = {kind: ", ".join(item.name for item in current)}
    if kind == "stages":
        described["stage summaries"] = "; ".join(f"{item.name}: {item.summary}" for item in current if item.summary)
    return described


@admin_only
@require_POST
def edit_items(request, pk, kind):
    model, noun, _ = ITEM_KINDS[kind]
    topic = get_object_or_404(Topic, pk=pk)
    items = getattr(topic, kind).all()
    before = describe_items(kind, items)
    try:
        with transaction.atomic():
            message = apply_item_action(model, noun, topic, items, request.POST)
            after = describe_items(kind, items)
            if after != before:
                CatalogChange.record(request.user, topic, Action.UPDATE, before, after)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, message)
    return redirect("manage:topic_edit", pk=pk)
