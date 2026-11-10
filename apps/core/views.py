"""The home page, the health check, the site search and the history page for any item."""

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import can_view, can_view_history, permission_required_for
from apps.ui.bands import make_band

from .models import AuditEvent
from .search import GROUP_LABELS, run_search, query_words
from .selectors import search_items
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


@view_allowed
def search(request):
    """Search guides, controls, risks, the Library and topics. Only published content is searched."""
    query = request.GET.get("q", "").strip()[:200]
    results, left_out = ({}, []) if not query_words(query) else run_search(query, search_items())
    groups = [(GROUP_LABELS[group], found) for group, found in results.items()]
    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "search_query": query,
            "groups": groups,
            "total": sum(len(found) for _, found in groups),
            "left_out": left_out,
            "band": make_band([], title="Search"),
            "show_comment_box": False,
        },
    )


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
