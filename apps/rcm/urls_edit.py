"""The web addresses for creating and editing controls, risks and evidence rules."""

from django.urls import path

from . import views_edit

# Prefixes keep clear of the read pages' controls/<ident>/ patterns.
urlpatterns = [
    path("new/control/", views_edit.control_new, name="control_new"),
    path("edit/control/<str:ident>/", views_edit.control_edit, name="control_edit"),
    path("new/risk/", views_edit.risk_new, name="risk_new"),
    path("edit/risk/<str:ident>/", views_edit.risk_edit, name="risk_edit"),
    path("new/evidence-rule/", views_edit.evidence_rule_new, name="evidence_rule_new"),
    path("edit/evidence-rule/<int:pk>/", views_edit.evidence_rule_edit, name="evidence_rule_edit"),
    path("topic-options/", views_edit.topic_options, name="topic_options"),
]
