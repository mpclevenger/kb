"""Create and edit pages and FAQ questions. Every save lands as a draft, for Tech Risk only."""

from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.accounts.permissions import can_propose, permission_required_for
from apps.core import versioning as v
from apps.rcm.views_edit import Flow, run_flow

from .forms import FaqForm, PageForm, starter_body
from .models import Faq, FaqVersion, Page, PageVersion, unique_page_slug
from .views_read import NAV_ACTIVE


class PageFlow(Flow):
    noun = "page"
    template = "wiki/page_form.html"
    form_class = PageForm
    nav_active = NAV_ACTIVE

    def list_url(self):
        return reverse("wiki:index")

    def create(self, user, form):
        content = self.payload(form)
        content["body"] = content["body"] or starter_body(content["section"])
        return v.create_entity(Page, PageVersion, user, {"slug": unique_page_slug(content["title"])}, **content)


class FaqFlow(Flow):
    noun = "question"
    template = "wiki/faq_form.html"
    form_class = FaqForm
    nav_active = NAV_ACTIVE

    def list_url(self):
        return reverse("wiki:faq")

    def initial(self, version):
        data = super().initial(version)
        data["related_pages"] = list(version.related_pages.values_list("pk", flat=True))
        return data

    def create(self, user, form):
        return v.create_entity(Faq, FaqVersion, user, {}, **self.payload(form))

    def after_save(self, version, user, form):
        version.related_pages.set(form.cleaned_data["related_pages"])


PAGE, FAQ = PageFlow(), FaqFlow()


@permission_required_for(can_propose)
def page_new(request):
    return run_flow(request, PAGE)


@permission_required_for(can_propose)
def page_edit(request, slug):
    return run_flow(request, PAGE, get_object_or_404(Page, slug=slug))


@permission_required_for(can_propose)
def faq_new(request):
    return run_flow(request, FAQ)


@permission_required_for(can_propose)
def faq_edit(request, pk):
    return run_flow(request, FAQ, get_object_or_404(Faq, pk=pk))
