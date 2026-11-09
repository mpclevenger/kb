"""The web addresses for the risk, control and driver pages, the explorer and the engine risks list."""

from django.urls import path

from . import urls_edit, views_read

app_name = "rcm"

urlpatterns = [
    path("", views_read.explorer, name="explorer"),
    path("sox/", views_read.sox_controls, name="sox"),
    path("controls/<str:ident>/", views_read.control_detail, name="control"),
    path("risks/<str:ident>/", views_read.risk_detail, name="risk"),
    path("drivers/<str:ident>/", views_read.driver_detail, name="driver"),
    path("engine-risks/", views_read.engine_risks, name="engine_risks"),
    path("evidence-rules/", views_read.evidence_rule_list, name="evidence_rules"),
    *urls_edit.urlpatterns,
]
