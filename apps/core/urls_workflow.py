"""The web addresses behind the Submit, Approve, Reject, Withdraw and Publish buttons."""

from django.urls import path

from . import retire, workflow

app_name = "workflow"
urlpatterns = [
    path("<int:type_id>/<int:version_id>/submit/", workflow.submit_view, name="submit"),
    path("<int:type_id>/<int:version_id>/withdraw/", workflow.withdraw_view, name="withdraw"),
    path("<int:type_id>/<int:version_id>/approve/", workflow.approve_view, name="approve"),
    path("<int:type_id>/<int:version_id>/reject/", workflow.reject_view, name="reject"),
    path("<int:type_id>/<int:version_id>/discard/", workflow.discard_view, name="discard"),
    path("<int:type_id>/item/<int:entity_id>/retire/", retire.retire_view, name="retire"),
]
