"""What a detail page for any governed item needs: which version to show, notices, footer and actions."""

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.urls import reverse

from apps.accounts import permissions

from .retire import retire_url
from .versioning import Kind, Status


def person(user):
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


@dataclass
class Resolved:
    entity: object
    version: object
    is_draft: bool
    is_retired: bool
    review_notice: dict | None


def resolve_version(request, entity):
    """Pick the version to show, or raise Http404 when the viewer may not see one."""
    user = request.user
    published = entity.version_as_of()
    open_ = entity.open_proposal()
    requested = request.GET.get("version")
    if requested is not None:
        if not requested.isdigit():
            raise Http404
        version = entity.versions.filter(number=int(requested)).first()
        if version is None or not permissions.can_see_version(user, version):
            raise Http404
    elif published is not None:
        version = published
    elif open_ is not None and permissions.can_see_version(user, open_):
        version = open_
    else:
        raise Http404

    notice = None
    if published is not None and open_ is not None and version.pk != open_.pk:
        can_open = permissions.can_see_version(user, open_)
        notice = {
            "drafting": open_.status == Status.DRAFT,
            "proposer": person(open_.proposed_by) if permissions.is_tech_risk(user) else None,
            "number": open_.number if can_open else None,
        }
    is_draft = version.status != Status.PUBLISHED
    return Resolved(
        entity=entity,
        version=version,
        is_draft=is_draft,
        is_retired=not is_draft and version.kind == Kind.RETIRE,
        review_notice=notice,
    )


def history_url(request, entity):
    if not permissions.can_view_history(request.user):
        return None
    return reverse("core:history", args=[ContentType.objects.get_for_model(entity).pk, entity.pk])


def footer(item):
    version = item.version
    return {
        "number": version.number,
        "effective": version.effective_from,
        "approver": person(version.decided_by) or "Not yet approved",
        "owner": version.owner_role,
        "review_by": version.review_by,
    }


def page_actions(request, item, edit_url):
    """Propose and Retire buttons and the workflow area for a detail page whose edit form is at `edit_url`.

    `edit_url` is None for items that have no form in the site (risk drivers); they can still be retired."""
    user = request.user
    can_edit = (
        permissions.can_propose(user)
        and not item.is_draft
        and not item.is_retired
        and item.entity.open_proposal() is None
    )
    own_draft = (
        item.version.status == Status.DRAFT
        and user.is_authenticated
        and item.version.proposed_by_id == user.pk
    )
    return {
        "propose_url": edit_url if can_edit else None,
        "retire_url": retire_url(item.entity) if can_edit else None,
        "edit_draft_url": edit_url if own_draft else None,
        "show_workflow": item.is_draft,
    }
