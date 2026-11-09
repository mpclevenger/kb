"""Who may do what to a governed version, and in which state.

This is the one place for these rules. The engine (versioning.py) enforces them and the
workflow buttons on the page (workflow_tags.py) use the same functions to decide what to show.
"""

from django.conf import settings

from apps.accounts.permissions import can_approve

from .versioning import Status

# action -> (state the version must be in, who may do it)
PROPOSER = "the proposer"
APPROVER = "an approver other than the proposer"
ACTIONS = {
    "edit": (Status.DRAFT, PROPOSER),
    "discard": (Status.DRAFT, PROPOSER),
    "submit": (Status.DRAFT, PROPOSER),
    "withdraw": (Status.IN_REVIEW, PROPOSER),
    "approve": (Status.IN_REVIEW, APPROVER),
    "reject": (Status.IN_REVIEW, APPROVER),
}

PROPOSER_ONLY_MESSAGES = {
    "edit": "Only the proposer can edit a draft.",
    "discard": "Only the proposer can discard a draft.",
    "submit": "Only the proposer can submit a draft.",
    "withdraw": "Only the proposer can withdraw.",
}
OWN_PROPOSAL_MESSAGES = {
    "approve": "You can't approve your own proposal.",
    "reject": "You can't reject your own proposal. Withdraw it instead.",
}


def why_not(action, version, user):
    """Why `user` may not `action` this version, ignoring its state; None when they may."""
    _, who = ACTIONS[action]
    is_proposer = version.proposed_by_id == user.pk
    if who == PROPOSER:
        return None if is_proposer else PROPOSER_ONLY_MESSAGES[action]
    if not can_approve(user):
        return f"You can't {action} changes."
    if is_proposer and not settings.ALLOW_SELF_APPROVAL:
        return OWN_PROPOSAL_MESSAGES[action]
    return None


def allowed_actions(version, user):
    """The set of actions `user` may take on `version` right now."""
    if not user.is_authenticated:
        return set()
    return {
        action
        for action, (status, _) in ACTIONS.items()
        if version.status == status and why_not(action, version, user) is None
    }
