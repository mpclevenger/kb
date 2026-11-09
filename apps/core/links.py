"""A helper that builds a page address only when that page exists."""

from django.urls import NoReverseMatch, reverse


def reverse_if_exists(name):
    """The URL for `name`, or None when no such route exists yet."""
    try:
        return reverse(name)
    except NoReverseMatch:
        return None
