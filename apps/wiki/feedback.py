"""Handles visitor comments on a page, and Tech Risk's replies to them."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.accounts.permissions import can_approve, can_view

from .models import Feedback, FeedbackStatus


def leave_feedback(user, about_url, about_label, section, comment):
    if not can_view(user):
        raise PermissionDenied("You can't leave comments.")
    if not comment.strip():
        raise ValidationError("Write a comment first.")
    if not about_url.startswith("/") or about_url.startswith("//"):
        raise ValidationError("Comments can only be left on pages in TRAC.")
    return Feedback.objects.create(
        about_url=about_url, about_label=about_label, section=section, comment=comment.strip(), submitted_by=user
    )


def respond(feedback, user, status, response=""):
    if not can_approve(user):
        raise PermissionDenied("Only Tech Risk can respond to comments.")
    if status == FeedbackStatus.DECLINED and not response.strip():
        raise ValidationError("Say why when declining.")
    feedback.status = status
    feedback.response = response
    feedback.handled_by = user
    feedback.handled_at = timezone.now()
    feedback.save()
    return feedback
