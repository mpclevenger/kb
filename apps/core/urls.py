"""The web addresses for the home page, the health check and the history page."""

from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("health/", views.health, name="health"),
    path("history/<int:type_id>/<int:entity_id>/", views.entity_history, name="history"),
    path("", views.home, name="home"),
]
