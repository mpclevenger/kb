"""The web addresses for leaving comments and for the Review queue."""

from django.urls import path

from . import views

app_name = "review"

urlpatterns = [
    path("", views.queue, name="queue"),
    path("comment/", views.comment, name="comment"),
    path("comments/<int:pk>/respond/", views.respond, name="respond"),
    path("my-comments/", views.mine, name="mine"),
]
