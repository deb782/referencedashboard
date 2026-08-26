"""Test dashboard pivot heads for CVF and vault stream visibility."""
import os
import pytest
import requests

BASE = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2").read().strip()
CVF = "proj_01d7e89ba838"
VV = "proj_53fb360c1f0a"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE}/api/auth/login", json={"phone": "9513242807", "password": "Repro@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def dash(admin_headers):
    r = requests.get(f"{BASE}/api/dashboard", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _find(dash, pid):
    return next((p for p in dash["by_project"] if p["project_id"] == pid), None)


def test_cvf_has_vault_flag(dash):
    cvf = _find(dash, CVF)
    assert cvf is not None, "CVF project missing from dashboard"
    assert cvf.get("has_vault") is True, f"CVF has_vault must be True, got {cvf.get('has_vault')}"
    assert "streams" in cvf and "land" in cvf["streams"] and "vault" in cvf["streams"]


def test_vv_no_vault(dash):
    vv = _find(dash, VV)
    assert vv is not None
    assert not vv.get("has_vault"), "VV must NOT be vault-enabled"


def test_cvf_pivot_has_many_components(dash):
    cvf = _find(dash, CVF)
    pivots = cvf.get("pivots", [])
    labels = " | ".join(p.get("label", "").lower() for p in pivots)
    keys = [p["key"] for p in pivots]
    # Required charge heads per problem statement
    expected_substrings = ["bsp", "gst", "plc", "legal", "electric", "khata",
                           "advance maintenance", "club", "ifms", "sinking", "stamp"]
    missing = [k for k in expected_substrings if k not in labels]
    assert not missing, f"CVF pivot missing components: {missing}. Have labels: {labels}. Keys: {keys}"
    # grand total row
    assert any(p.get("tag") == "total" for p in pivots), "Grand total row missing"
    assert len(pivots) >= 12, f"Expected >=12 pivot rows incl total, got {len(pivots)}"


def test_consolidated_has_vault_fields(dash):
    con = dash.get("consolidated", {})
    for k in ("land_booked", "land_received", "vault_booked", "vault_received", "vault_attach"):
        assert k in con, f"consolidated.{k} missing"


def test_vv_pivot_still_works(dash):
    vv = _find(dash, VV)
    # VV should have pivots too (its own components) and no vault stream
    assert isinstance(vv.get("pivots"), list)
    assert vv.get("has_vault") in (False, None)
