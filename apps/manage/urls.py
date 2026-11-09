"""The web addresses for the Manage screens."""

from django.urls import path

from . import common, views_aspects, views_platforms, views_topics

app_name = "manage"

urlpatterns = [
    path("", views_platforms.index, name="index"),
    # Topics, their stages and themes
    path("topics/new/", views_topics.topic_edit, name="topic_new"),
    path("topics/<int:pk>/", views_topics.topic_edit, name="topic_edit"),
    path("topics/<int:pk>/active/", common.set_active, {"model_name": "topic"}, name="topic_active"),
    path("topics/<int:pk>/stages/", views_topics.edit_items, {"kind": "stages"}, name="stages"),
    path("topics/<int:pk>/themes/", views_topics.edit_items, {"kind": "themes"}, name="themes"),
    # Platforms
    path("platforms/new/", views_platforms.platform_edit, name="platform_new"),
    path("platforms/<int:pk>/", views_platforms.platform_edit, name="platform_edit"),
    path("platforms/<int:pk>/active/", common.set_active, {"model_name": "platform"}, name="platform_active"),
    # Aspect questions
    path("aspects/", views_aspects.aspect_list, name="aspect_list"),
    path("aspects/new/", views_aspects.aspect_edit, name="aspect_new"),
    path("aspects/<int:pk>/", views_aspects.aspect_edit, name="aspect_edit"),
    path("aspects/<int:pk>/delete/", views_aspects.aspect_delete, name="aspect_delete"),
]
