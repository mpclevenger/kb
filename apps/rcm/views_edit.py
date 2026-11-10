"""Create and edit pages for controls, risks and evidence rules.

Every save lands as a draft. Making a draft official goes through the workflow
actions in apps.core.workflow.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.accounts.permissions import can_propose, permission_required_for
from apps.core import versioning as v
from apps.topics.models import Stage, Theme

from . import services
from .forms import ControlForm, EvidenceRuleForm, RiskForm
from .models import (
    Control,
    EvidenceRule,
    EvidenceRuleVersion,
    Risk,
)

SAVED = "Draft saved. Check it over, then submit it for review when you're ready."


class Flow:
    """How one kind of register item is created, changed and shown on its form."""

    noun = ""
    template = ""
    form_class = None
    entity_model = None
    nav_active = "rcm"

    def list_url(self):
        return reverse("rcm:explorer")

    def entity_url(self, entity):
        return entity.get_absolute_url()

    def initial(self, version):
        data = {}
        for name in self.form_class.base_fields:
            if name == "change_summary":
                continue
            if hasattr(version, f"{name}_id"):
                data[name] = getattr(version, f"{name}_id")
            elif hasattr(version, name):
                data[name] = getattr(version, name)
        return data

    def form_kwargs(self, version):
        return {}

    def payload(self, form):
        return form.content()

    def create(self, user, form):
        raise NotImplementedError

    def after_save(self, version, user, form):
        pass

    def save(self, user, form, entity, draft):
        """Create the item, update the user's own draft, or propose a new version. Returns (entity, version)."""
        content = self.payload(form)
        if "change_summary" in form.cleaned_data:  # the form leaves it out for a first draft
            content["change_summary"] = form.cleaned_data["change_summary"]
        with transaction.atomic():
            if entity is None:
                entity, version = self.create(user, form)
            elif draft is not None:
                version = v.update_draft(draft, user, **content)
            else:
                version = v.propose_change(entity, user, **content)
            self.after_save(version, user, form)
        return entity, version


class ControlFlow(Flow):
    noun = "control"
    template = "rcm/control_form.html"
    form_class = ControlForm
    entity_model = Control

    asks_for_id = True

    def create(self, user, form):
        content = self.payload(form)
        topic = content.pop("topic")
        return services.create_control(user, topic, ident=form.cleaned_data["ident"], **content)

    def initial(self, version):
        data = super().initial(version)
        data["platforms"] = list(version.platforms.values_list("pk", flat=True))
        return data

    def after_save(self, version, user, form):
        version.platforms.set(form.cleaned_data["platforms"])


class RiskFlow(Flow):
    noun = "risk"
    template = "rcm/risk_form.html"
    form_class = RiskForm
    entity_model = Risk

    asks_for_id = True

    def create(self, user, form):
        content = self.payload(form)
        topic = content.pop("topic")
        return services.create_risk(user, topic, ident=form.cleaned_data["ident"], **content)

    def initial(self, version):
        data = super().initial(version)
        data["controls"] = [
            {"control": link.control.ident, "coverage": link.coverage, "rationale": link.rationale}
            for link in version.control_links.select_related("control").order_by("control__ident")
        ]
        data["drivers"] = list(version.driver_links.values_list("driver_id", flat=True))
        return data

    def form_kwargs(self, version):
        if version is None:
            return {}
        return {
            "linked_controls": [link.control for link in version.control_links.select_related("control")],
        }

    def after_save(self, version, user, form):
        services.set_risk_links(
            version, user, controls=form.cleaned_data["controls"], drivers=form.cleaned_data["drivers"]
        )


class EvidenceRuleFlow(Flow):
    noun = "evidence rule"
    template = "rcm/evidence_rule_form.html"
    form_class = EvidenceRuleForm
    entity_model = EvidenceRule

    def list_url(self):
        return reverse("rcm:evidence_rules")

    def entity_url(self, entity):
        return reverse("rcm:evidence_rule_edit", args=[entity.pk])

    def create(self, user, form):
        return v.create_entity(EvidenceRule, EvidenceRuleVersion, user, {}, **self.payload(form))


CONTROL, RISK, EVIDENCE = ControlFlow(), RiskFlow(), EvidenceRuleFlow()


def _starting_point(entity):
    published = entity.versions.filter(status=v.Status.PUBLISHED).order_by("-number").first()
    return published or entity.versions.order_by("-number").first()


def _blocked_message(user, entity, open_version):
    if open_version is None:
        return f"{entity} is retired, so it can't be changed."
    if open_version.proposed_by_id == user.pk:
        return (
            f"Your change to {entity} (version {open_version.number}) is in review. "
            "Withdraw it if you want to edit it again."
        )
    return (
        f"Someone else is already working on a change to {entity} "
        f"(version {open_version.number}, {open_version.get_status_display().lower()}). "
        "Changes go one at a time, so wait until it is approved, rejected or withdrawn."
    )


def _view_link(flow, entity, version):
    if version is None:
        return None
    return f"{flow.entity_url(entity)}?version={version.number}"


def run_flow(request, flow, entity=None):
    """Show and save the form for one register item.

    No entity means a new item. An entity with the user's own draft edits that draft.
    An entity without an open proposal starts a new version from the latest published one.
    If someone else has an open proposal, or the item is retired, show why it can't be edited.
    A valid POST saves a draft and redirects to it.
    """
    user = request.user
    draft = base = None
    if entity is not None:
        open_ = entity.open_proposal()
        if open_ is not None:
            if open_.status == v.Status.DRAFT and open_.proposed_by_id == user.pk:
                draft = open_
            else:
                return _blocked(request, flow, entity, open_)
        elif entity.is_retired():
            return _blocked(request, flow, entity, None)
        else:
            base = _starting_point(entity)
    source = draft or base
    makes_new_version = entity is not None and (draft.number > 1 if draft else True)
    kwargs = {"with_summary": makes_new_version, **flow.form_kwargs(source)}
    if entity is None and getattr(flow, "asks_for_id", False):
        kwargs["with_ident"] = True  # a new control or risk takes its ID from the RCM

    if request.method == "POST":
        form = flow.form_class(request.POST, **kwargs)
        if form.is_valid():
            try:
                saved_entity, version = flow.save(user, form, entity, draft)
            except ValidationError as error:
                form.add_error(None, error.messages)
            else:
                messages.success(request, SAVED)
                return redirect(f"{flow.entity_url(saved_entity)}?version={version.number}")
    else:
        form = flow.form_class(initial=flow.initial(source) if source else None, **kwargs)

    context = _context(flow, entity, form, draft)
    return render(request, flow.template, context)


def _context(flow, entity, form, draft):
    if entity is None:
        heading, ident = f"New {flow.noun}", None
    elif draft is not None:
        heading, ident = f"Edit draft {flow.noun}", str(entity)
    else:
        heading, ident = f"Edit {flow.noun}", str(entity)
    return {
        "nav_active": flow.nav_active,
        "form": form,
        "heading": heading,
        "ident": ident,
        "entity": entity,
        "version": draft,
        "noun": flow.noun,
        "cancel_url": flow.entity_url(entity) if entity is not None else flow.list_url(),
    }


def _blocked(request, flow, entity, open_version):
    user = request.user
    context = {
        "nav_active": flow.nav_active,
        "heading": f"Edit {flow.noun}",
        "ident": str(entity),
        "entity": entity,
        "noun": flow.noun,
        "blocked": _blocked_message(user, entity, open_version),
        "view_link": _view_link(flow, entity, open_version),
        "version": open_version,
        "cancel_url": flow.entity_url(entity),
    }
    return render(request, flow.template, context)


def _new(flow):
    @permission_required_for(can_propose)
    def view(request):
        return run_flow(request, flow)

    return view


def _edit(flow, lookup_field):
    """Edit view for the item whose `lookup_field` (also the URL keyword) matches."""

    @permission_required_for(can_propose)
    def view(request, **kwargs):
        entity = get_object_or_404(flow.entity_model, **{lookup_field: kwargs[lookup_field]})
        return run_flow(request, flow, entity)

    return view


control_new = _new(CONTROL)
control_edit = _edit(CONTROL, "ident")
risk_new = _new(RISK)
risk_edit = _edit(RISK, "ident")
evidence_rule_new = _new(EVIDENCE)
evidence_rule_edit = _edit(EVIDENCE, "pk")


def _options(items, empty_label):
    options = format_html_join("", '<option value="{}">{}</option>', ((i.pk, i.name) for i in items))
    return format_html('<option value="">{}</option>{}', empty_label, options)


@permission_required_for(can_propose)
def topic_options(request):
    """Stage <option> tags for the chosen topic, swapped into the stage select by HTMX.

    The topic's theme options ride along as an out-of-band swap into the theme select.
    """
    topic_id = request.GET.get("topic", "")
    topic_id = int(topic_id) if topic_id.isdigit() else None
    stages = Stage.objects.filter(topic_id=topic_id)
    themes = Theme.objects.filter(topic_id=topic_id)
    return HttpResponse(
        format_html(
            '{}<select id="id_theme" hx-swap-oob="innerHTML">{}</select>',
            _options(stages, "No specific stage"),
            _options(themes, "No theme"),
        )
    )
