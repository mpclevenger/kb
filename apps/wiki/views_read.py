"""Read pages: the best practices and guides index, wiki pages and the FAQ."""

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

from apps.accounts import permissions
from apps.core import detail
from apps.ui.bands import make_band

from . import selectors
from .models import Faq, Page, Section
from .richtext import add_heading_anchors, clean_html, split_sections

NAV_ACTIVE = "guides"
TITLE = "Best practices and guides"
can_view = permissions.permission_required_for(permissions.can_view)

SECTION_HINTS = {
    Section.BUILD: "How to design and set up a control.",
    Section.RUN: "How to run a control well, period after period.",
    Section.BEST_PRACTICE: "Good practice for a technology or risk area.",
    Section.AUDIT_PREP: "What to expect from an audit and how to prepare.",
}
COLLAPSE_FROM = 5  # guides with this many sections or more open with every section collapsed
FAQ_SENTENCE = "Short answers to common questions, with links to the full guidance."


def _crumbs(*trail):
    """Home / Best practices and guides / ..., where `trail` is (label, url or None) pairs."""
    return [("Home", "/"), (TITLE, reverse("wiki:index"))] + list(trail)


def _new_button(request, label, url_name):
    if not permissions.can_propose(request.user):
        return None
    return (label, reverse(url_name))


@can_view
@vary_on_headers("HX-Request")
def index(request):
    section = request.GET.get("section", "")
    if section not in Section.values:
        section = ""
    pages = selectors.current_pages()
    context = {
        "nav_active": NAV_ACTIVE,
        "cards": [
            {
                "key": key,
                "label": label,
                "hint": SECTION_HINTS[key],
                "active": key == section,
            }
            for key, label in Section.choices
        ],
        "rows": [(p, v) for p, v in pages if not section or v.section == section],
        "new_button": _new_button(request, "New page", "wiki:page_new"),
        "band": make_band([("Home", "/"), (TITLE, None)], title=TITLE),
    }
    template = "wiki/_library.html" if request.headers.get("HX-Request") else "wiki/index.html"
    return render(request, template, context)


@can_view
def page(request, slug):
    if slug in selectors.MERGED_GUIDES:
        return redirect("wiki:page", selectors.MERGED_GUIDES[slug], permanent=True)
    item = detail.resolve_version(request, get_object_or_404(Page, slug=slug))
    version = item.version
    body, toc = add_heading_anchors(clean_html(version.body))
    intro, sections = split_sections(body)
    context = {
        "nav_active": NAV_ACTIVE,
        "item": item,
        "v": version,
        "body": mark_safe(body),
        # Each h2 section is shown as a card. Long guides start collapsed so they read as a list.
        "intro": mark_safe(intro),
        # A section holding a diagram always starts open, so the diagram is seen first.
        "sections": [
            {
                **section,
                "html": mark_safe(section["html"]),
                "open": len(sections) < COLLAPSE_FROM or 'class="mermaid"' in section["html"],
            }
            for section in sections
        ],
        "toc": toc,
        "footer": detail.footer(item),
        "history_url": detail.history_url(request, item.entity),
        **detail.page_actions(request, item, reverse("wiki:page_edit", args=[item.entity.slug])),
        "band": make_band(_crumbs((version.title, None)), title=version.title, section=version.section),
    }
    return render(request, "wiki/page.html", context)


@can_view
def audit_prep(request):
    return redirect(f"{reverse('wiki:index')}?section={Section.AUDIT_PREP}")


@can_view
def faq(request):
    context = {
        "nav_active": NAV_ACTIVE,
        "groups": selectors.faq_groups(),
        "can_propose": permissions.can_propose(request.user),
        "new_button": _new_button(request, "New question", "wiki:faq_new"),
        "band": make_band(_crumbs(("FAQ", None)), title="Frequently asked questions", summary=FAQ_SENTENCE),
    }
    return render(request, "wiki/faq.html", context)


@can_view
def faq_detail(request, pk):
    item = detail.resolve_version(request, get_object_or_404(Faq, pk=pk))
    version = item.version
    context = {
        "nav_active": NAV_ACTIVE,
        "item": item,
        "v": version,
        "related": selectors.related_current(version, selectors.pages_by_pk()),
        **detail.page_actions(request, item, reverse("wiki:faq_edit", args=[item.entity.pk])),
        "history_url": detail.history_url(request, item.entity),
        "band": make_band(
            _crumbs(("FAQ", reverse("wiki:faq")), ("Question", None)), title=version.question, summary=FAQ_SENTENCE
        ),
    }
    return render(request, "wiki/faq_detail.html", context)
