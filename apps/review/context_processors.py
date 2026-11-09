"""Decides which pages show the "Comment on this page" box."""

from apps.accounts.permissions import can_view

# The comment box is for reading pages. It is hidden on forms (any route named *_new or
# *_edit) and on the work areas listed here.
NO_COMMENT_NAMESPACES = {"manage", "review", "ui", "accounts", "admin"}


def comment_box(request):
    match = getattr(request, "resolver_match", None)
    is_form = match is not None and match.url_name and match.url_name.endswith(("_new", "_edit"))
    is_work_area = match is not None and match.namespace in NO_COMMENT_NAMESPACES
    user = getattr(request, "user", None)
    return {"show_comment_box": can_view(user) and not is_form and not is_work_area}
