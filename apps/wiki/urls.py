"""The web addresses for guides and the FAQ."""

from django.urls import path

from . import views_edit, views_read

app_name = "wiki"

# Fixed addresses come before the page slug pattern; unique_page_slug never issues these as slugs.
urlpatterns = [
    path("", views_read.index, name="index"),
    path("faq/", views_read.faq, name="faq"),
    path("faq/<int:pk>/", views_read.faq_detail, name="faq_detail"),
    path("audit-prep/", views_read.audit_prep, name="audit_prep"),
    path("new/page/", views_edit.page_new, name="page_new"),
    path("new/faq/", views_edit.faq_new, name="faq_new"),
    path("edit/page/<slug:slug>/", views_edit.page_edit, name="page_edit"),
    path("edit/faq/<int:pk>/", views_edit.faq_edit, name="faq_edit"),
    path("<slug:slug>/", views_read.page, name="page"),
]
