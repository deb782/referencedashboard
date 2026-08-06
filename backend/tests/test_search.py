"""Backend tests for /api/search role-scoped global search."""
import os
import requests
import pytest

def _base():
    b = os.environ.get("REACT_APP_BACKEND_URL")
    if not b:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    b = line.split("=", 1)[1].strip()
                    break
    return b.rstrip("/") + "/api"

BASE = _base()

CREDS = {
    "admin": ("9999999999", "Repro@123"),
    "accounts": ("9000000001", "Accounts@123"),
    "post_sales": ("9000000002", "Sales@123"),
    "site_manager": ("9000000003", "Site@123"),
}


def _tok(role):
    p, pw = CREDS[role]
    r = requests.post(f"{BASE}/auth/login", json={"phone": p, "password": pw}, timeout=20)
    assert r.status_code == 200, f"{role} login failed: {r.text}"
    return r.json()["access_token"]


def _search(tok, q):
    r = requests.get(f"{BASE}/search", params={"q": q}, headers={"Authorization": f"Bearer {tok}"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["results"]


@pytest.fixture(scope="module")
def tokens():
    return {r: _tok(r) for r in CREDS}


def test_min_query_length(tokens):
    assert _search(tokens["admin"], "a") == []
    assert _search(tokens["admin"], "") == []


def test_admin_ravi_finds_plot(tokens):
    res = _search(tokens["admin"], "Ravi")
    types = {r["type"] for r in res}
    assert "unit" in types, f"Expected unit result, got {res}"
    unit = next(r for r in res if r["type"] == "unit")
    assert unit["link"] == "/units"
    assert "16" in unit["label"] or "Plot" in unit["label"]


def test_admin_vacation_finds_project(tokens):
    res = _search(tokens["admin"], "Vacation")
    types = {r["type"] for r in res}
    assert "project" in types
    proj = next(r for r in res if r["type"] == "project")
    assert proj["link"] == "/projects"


def test_admin_finds_team(tokens):
    # phone 9000000001 is Accounts user
    res = _search(tokens["admin"], "9000000001")
    types = {r["type"] for r in res}
    assert "user" in types, f"Admin should see team results, got {res}"


def test_admin_finds_inventory_and_procurement(tokens):
    inv = _search(tokens["admin"], "Cement")
    assert any(r["type"] == "inventory" for r in inv), f"Expected inventory, got {inv}"
    proc = _search(tokens["admin"], "Regr")
    assert any(r["type"] == "procurement" for r in proc), f"Expected procurement, got {proc}"


def test_site_manager_scope(tokens):
    res = _search(tokens["site_manager"], "Ravi")
    # Should return only project-scoped items and NO user results
    types = {r["type"] for r in res}
    assert "user" not in types, f"Site manager must not see users, got {res}"
    # Inventory/procurement should be scoped; searching 'Cement' should stay within project
    inv = _search(tokens["site_manager"], "Cement")
    for r in inv:
        assert r["type"] in ("inventory", "unit", "procurement"), r
        assert r["type"] != "user"


def test_site_manager_no_team_results(tokens):
    res = _search(tokens["site_manager"], "Admin")
    assert not any(r["type"] == "user" for r in res)


def test_accounts_no_inventory_no_team(tokens):
    # Search a term likely present in inventory and users
    res = _search(tokens["accounts"], "Cement")
    types = {r["type"] for r in res}
    assert "inventory" not in types, f"Accounts must not see inventory, got {res}"
    assert "user" not in types, f"Accounts must not see users, got {res}"

    res2 = _search(tokens["accounts"], "Admin")
    assert not any(r["type"] == "user" for r in res2)


def test_accounts_sees_units_projects_procurement(tokens):
    res = _search(tokens["accounts"], "Vacation")
    assert any(r["type"] == "project" for r in res)
    res2 = _search(tokens["accounts"], "Ravi")
    assert any(r["type"] == "unit" for r in res2)


def test_post_sales_no_inventory_no_procurement_no_team(tokens):
    res = _search(tokens["post_sales"], "Cement")
    types = {r["type"] for r in res}
    assert "inventory" not in types
    assert "user" not in types
    assert "procurement" not in types
    # Should still see units/projects
    res2 = _search(tokens["post_sales"], "Vacation")
    assert any(r["type"] == "project" for r in res2)


def test_unauthenticated_rejected():
    r = requests.get(f"{BASE}/search", params={"q": "Ravi"}, timeout=20)
    assert r.status_code in (401, 403)
