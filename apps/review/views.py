"""The pages for leaving a comment, seeing your own comments, and the Tech Risk Review queue."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.permissions import can_approve, can_view, permission_required_for
from apps.wiki import feedback
from apps.wiki.models import Feedback, FeedbackStatus

from .selectors import item_name, type_label, versions_in_review, view_url

ALL = "all"

approvers_only = permission_required_for(can_approve)
readers_only = permission_required_for(can_view)


def _safe_path(path):
    """The page the comment was left on, or My comments when the path isn't a local one."""
    # allowed_hosts=None accepts only paths on this site (no other host, no scheme).
    if url_has_allowed_host_and_scheme(path, allowed_hosts=None):
        return path
    return reverse("review:mine")


@readers_only
@require_POST
def comment(request):
    path = request.POST.get("path", "")
    try:
        feedback.leave_feedback(
            request.user,
            path,
            request.POST.get("label", "").strip()[:200] or path,
            request.POST.get("section", "General")[:80],
            request.POST.get("comment", ""),
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(
            request,
            format_html(
                'Thanks — your comment was sent to Tech Risk. See replies under <a href="{}">My comments</a>.',
                reverse("review:mine"),
            ),
        )
    return redirect(_safe_path(path))


@readers_only
def mine(request):
    comments = Feedback.objects.filter(submitted_by=request.user)
    return render(request, "review/mine.html", {"comments": comments})


@approvers_only
def queue(request):
    status = request.GET.get("status", FeedbackStatus.NEW)
    counts = dict(Feedback.objects.values_list("status").annotate(Count("pk")))
    comments = Feedback.objects.select_related("submitted_by")
    versions = [
        {"version": version, "name": item_name(version), "type": type_label(version), "url": view_url(version)}
        for version in versions_in_review()
    ]
    return render(
        request,
        "review/queue.html",
        {
            "nav_active": "review",
            "versions": versions,
            "status": status,
            "statuses": [(ALL, "All", sum(counts.values()))]
            + [(value, label, counts.get(value, 0)) for value, label in FeedbackStatus.choices],
            "status_choices": FeedbackStatus.choices,
            "comments": comments if status == ALL else comments.filter(status=status),
        },
    )


@approvers_only
@require_POST
def respond(request, pk):
    item = get_object_or_404(Feedback, pk=pk)
    status = request.POST.get("status", "")
    if status not in FeedbackStatus.values:
        return HttpResponseBadRequest("Unknown status.")
    try:
        feedback.respond(item, request.user, status, request.POST.get("response", "").strip())
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Saved.")
    back_to = request.POST.get("view", "")
    if back_to != ALL and back_to not in FeedbackStatus.values:
        back_to = FeedbackStatus.NEW
    return redirect(f"{reverse('review:queue')}?status={back_to}")
