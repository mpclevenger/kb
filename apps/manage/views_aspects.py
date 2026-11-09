"""Aspect question pages."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.platforms.models import AspectQuestion

from .common import Action, admin_only, edit_page
from .forms import AspectQuestionForm
from .models import CatalogChange, snapshot


@admin_only
def aspect_list(request):
    return render(
        request, "manage/aspect_list.html", {"questions": AspectQuestion.objects.select_related("topic")}
    )


@admin_only
def aspect_edit(request, pk=None):
    question = get_object_or_404(AspectQuestion, pk=pk) if pk else None
    return edit_page(request, AspectQuestionForm, "manage/aspect_form.html", "manage:aspect_edit", question)


@admin_only
@require_POST
def aspect_delete(request, pk):
    question = get_object_or_404(AspectQuestion, pk=pk)
    fields = AspectQuestionForm._meta.fields
    with transaction.atomic():
        CatalogChange.record(request.user, question, Action.DELETE, snapshot(question, fields))
        question.delete()
    messages.success(request, f"Deleted aspect question: {question}.")
    return redirect("manage:aspect_list")
