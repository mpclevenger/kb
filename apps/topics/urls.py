"""The web addresses for the topic pages."""

from django.urls import path

from . import views

app_name = "topics"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.detail, name="detail"),
]
