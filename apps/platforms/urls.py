"""The web addresses for the category and platform pages."""

from django.urls import path

from . import views, views_edit

app_name = "platforms"

urlpatterns = [
    path("", views.index, name="index"),
    path("category/<slug:key>/", views.category, name="category"),
    path("category/<slug:key>/guidance/", views_edit.guidance_edit, name="guidance_edit"),
    path("<slug:slug>/guidance/", views_edit.guidance_edit, name="guidance_edit"),
    path("<slug:slug>/", views.detail, name="detail"),
]
