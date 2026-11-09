"""The site's front door: sends each web address to the app that handles it."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("ui/", include("apps.ui.urls")),
    path("workflow/", include("apps.core.urls_workflow")),
    path("rcm/", include("apps.rcm.urls")),
    path("topics/", include("apps.topics.urls")),
    path("platforms/", include("apps.platforms.urls")),
    path("manage/", include("apps.manage.urls")),
    path("review/", include("apps.review.urls")),
    path("guides/", include("apps.wiki.urls")),
]
