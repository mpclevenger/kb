"""The web addresses for signing in, signing out and "who am I"."""

from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("staff/", views.StaffLoginView.as_view(), name="staff_login"),
    path("logout/", views.logout_view, name="logout"),
    path("whoami/", views.whoami, name="whoami"),
]
