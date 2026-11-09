"""Checks the /health/ page that tells the hosting platform the site is up."""

from django.urls import reverse


def test_health_returns_ok(client, db):
    response = client.get(reverse("core:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_renders(client, db):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
