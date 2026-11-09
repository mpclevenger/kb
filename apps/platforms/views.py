"""Library pages: one page per category and one page per platform. The landing is Home (core:home)."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify

from apps.accounts import permissions
from apps.rcm.selectors import current_controls
from apps.ui.bands import make_band
from apps.wiki import selectors as wiki_selectors

from . import selectors
from .categories import CATEGORY_KEYS, Category, group_title
from .models import Platform

can_view = permissions.permission_required_for(permissions.can_view)


def _library_crumbs(category):
    group = group_title(category)
    return [("Library", reverse("core:home")), (group, f"{reverse('core:home')}#{slugify(group)}")]


@can_view
def index(request):
    return redirect("core:home")


@can_view
def category(request, key):
    if key not in CATEGORY_KEYS:
        raise Http404
    category = Category(key)
    guidance = selectors.current_guidance(category=key)
    members = selectors.category_platforms(key)
    controls = selectors.applicable_controls(current_controls(), categories=[key], platforms=members)
    edit_url = reverse("platforms:guidance_edit", kwargs={"key": key})
    context = {
        "nav_active": "library",
        "category": category,
        "band": make_band(
            [*_library_crumbs(category), (category.label, None)],
            title=category.label,
            summary=guidance.intro if guidance else "",
            action=_edit_button(request, edit_url),
        ),
        "members": members,
        "rows": selectors.aspect_rows(controls, selectors.active_questions(), guidance),
        "references": guidance.references if guidance else [],
    }
    return render(request, "platforms/category.html", context)


def _edit_button(request, edit_url):
    """The band's "Edit guidance" button, for people who can propose changes."""
    return ("Edit guidance", edit_url) if permissions.can_propose(request.user) else None


def _guides(platform):
    """Published wiki pages about this platform."""
    return [
        {"title": version.title, "section": version.section, "url": page.get_absolute_url()}
        for page, version in wiki_selectors.current_pages()
        if version.platform_id == platform.pk
    ]


@can_view
def detail(request, slug):
    platform = get_object_or_404(Platform, slug=slug, is_active=True)
    primary = Category(platform.primary_category)
    controls = current_controls()
    questions = selectors.active_questions()
    practices, references = [], []
    for key in platform.categories:
        guidance = selectors.current_guidance(category=key)
        rows = selectors.aspect_rows(selectors.applicable_controls(controls, categories=[key]), questions, guidance)
        practices.append({"category": Category(key), "rows": rows, "count": sum(row.has_content for row in rows)})
        references += guidance.references if guidance else []
    guidance = selectors.current_guidance(platform=platform)
    edit_url = reverse("platforms:guidance_edit", kwargs={"slug": platform.slug})
    references += guidance.references if guidance else []
    specific = selectors.aspect_rows(
        selectors.applicable_controls(controls, platforms=[platform]), questions, guidance
    )
    context = {
        "nav_active": "library",
        "platform": platform,
        "category": primary,
        "band": make_band(
            [
                *_library_crumbs(primary),
                (primary.label, reverse("platforms:category", args=[primary.value])),
                (platform.name, None),
            ],
            title=platform.name,
            summary=guidance.intro if guidance else "",
            action=_edit_button(request, edit_url),
        ),
        "practices": practices,
        "specific_rows": [row for row in specific if row.has_content],
        "guides": _guides(platform),
        "references": list({r["url"]: r for r in references}.values()),
        "edit_url": edit_url,
    }
    return render(request, "platforms/detail.html", context)
