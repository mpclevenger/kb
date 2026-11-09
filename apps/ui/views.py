"""The component gallery page, which shows every shared page piece in one place."""

from django.shortcuts import render

from .gallery import sample_context


def gallery(request):
    return render(request, "ui/gallery.html", {"nav_active": None, **sample_context()})
