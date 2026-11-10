"""The web addresses for the front page, the Library, the tool pages, the health check, the search and the history page."""

from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("health/", views.health, name="health"),
    path("search/", views.search, name="search"),
    path("history/<int:type_id>/<int:entity_id>/", views.entity_history, name="history"),
    path("library/", views.library, name="library"),
    path("tools/<slug:slug>/", views.tool, name="tool"),
    path("", views.home, name="home"),
]
