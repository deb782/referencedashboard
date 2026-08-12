"""Regression tests: post-startup-scrub, admin login and endpoint health."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://read-start-2.preview.emergentagent.com").rstrip("/")
ADMIN_PHONE = "9513242807"
ADMIN_PASS = "Repro@123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    assert "user" in data
    assert data["user"].get("role") == "admin"
    return data["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("access_token"), str) and len(body["access_token"]) > 10


def test_auth_me(headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=30)
    assert r.status_code == 200
    assert r.json().get("phone") == ADMIN_PHONE


def test_dashboard(headers):
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    # sanity - no NaN/Inf leaking (would fail JSON parse anyway)
    assert isinstance(body, dict)


def test_projects(headers):
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert r.status_code == 200
    projects = r.json()
    assert isinstance(projects, list) and len(projects) >= 2
    ids = [p.get("project_id") or p.get("id") for p in projects]
    assert "proj_53fb360c1f0a" in ids
    assert "proj_01d7e89ba838" in ids


@pytest.mark.parametrize("pid", ["proj_53fb360c1f0a", "proj_01d7e89ba838"])
def test_units_by_project(headers, pid):
    r = requests.get(f"{BASE_URL}/api/units", params={"project_id": pid}, headers=headers, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_notifications(headers):
    r = requests.get(f"{BASE_URL}/api/notifications", headers=headers, timeout=30)
    assert r.status_code == 200


def test_accounts_overview(headers):
    r = requests.get(f"{BASE_URL}/api/accounts/overview", headers=headers, timeout=30)
    assert r.status_code == 200


def test_cancellations(headers):
    r = requests.get(f"{BASE_URL}/api/cancellations", headers=headers, timeout=30)
    assert r.status_code == 200


def test_procurement(headers):
    r = requests.get(f"{BASE_URL}/api/procurement", headers=headers, timeout=30)
    assert r.status_code == 200


def test_users(headers):
    r = requests.get(f"{BASE_URL}/api/users", headers=headers, timeout=30)
    assert r.status_code == 200
