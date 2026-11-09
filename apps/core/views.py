"""The home page, the health check and the history page for any item."""

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import can_view, can_view_history, permission_required_for
from apps.ui.bands import make_band

from .models import AuditEvent
from .versioning import GovernedEntity

view_allowed = permission_required_for(can_view)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "database unavailable"}, status=503)


@view_allowed
def home(request):
    """The Library by technology is the home page."""
    return render(request, "platforms/library.html", {"nav_active": "library", "band": make_band([], title="Library")})


@permission_required_for(can_view_history)
def entity_history(request, type_id, entity_id):
    content_type = get_object_or_404(ContentType, pk=type_id)
    model = content_type.model_class()
    if model is None or not issubclass(model, GovernedEntity):
        raise Http404
    entity = get_object_or_404(model, pk=entity_id)
    return render(
        request,
        "core/history.html",
        {
            "entity": entity,
            "versions": entity.history().select_related(
                "proposed_by", "decided_by", "published_by"
            ),
            "events": AuditEvent.for_entity(entity).select_related("actor"),
        },
    )
