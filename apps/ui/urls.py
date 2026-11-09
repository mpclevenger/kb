"""The web address for the component gallery."""

from django.urls import path

from . import views

app_name = "ui"
urlpatterns = [
    path("gallery/", views.gallery, name="gallery"),
]
