"""
Phase-4 admin UI/logic edits — backend regression:
  1) GET /projects returns rate_per_sqft
  2) PATCH /projects/{id}/rate persists (admin-only)
  3) GET /dashboard by_project has total_units & sold; consolidated present for KPI row
  4) POST /units/{unit_id}/sell accepts empty buyer_name/buyer_contact
  5) Cleanup: revert unit + delete payments + delete notification
"""
import os, pytest, requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN = {"phone": "9513242807", "password": "Repro@123"}
VV = "proj_53fb360c1f0a"  # Vacation Village Chikkamagaluru
CVF = "proj_01d7e89ba838" # Central Vista Farms


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------- Projects: rate_per_sqft ----------------
def test_projects_expose_rate_per_sqft(h):
    r = requests.get(f"{BASE}/projects", headers=h, timeout=20)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 2
    for p in rows:
        assert "rate_per_sqft" in p
        assert isinstance(p["rate_per_sqft"], (int, float))


def test_patch_rate_persists_for_vv(h):
    # capture original
    r = requests.get(f"{BASE}/projects", headers=h).json()
    orig = next(x for x in r if x["project_id"] == VV)["rate_per_sqft"]

    new_val = 4321.5
    r2 = requests.patch(f"{BASE}/projects/{VV}/rate",
                        headers=h, json={"rate_per_sqft": new_val})
    assert r2.status_code == 200, r2.text
    assert r2.json()["rate_per_sqft"] == round(new_val, 2)

    # confirm via GET
    r3 = requests.get(f"{BASE}/projects", headers=h).json()
    got = next(x for x in r3 if x["project_id"] == VV)["rate_per_sqft"]
    assert got == round(new_val, 2)

    # restore
    requests.patch(f"{BASE}/projects/{VV}/rate", headers=h,
                   json={"rate_per_sqft": orig})


def test_patch_rate_unknown_project(h):
    r = requests.patch(f"{BASE}/projects/does_not_exist/rate",
                       headers=h, json={"rate_per_sqft": 100})
    assert r.status_code == 404


# ---------------- Dashboard shape ----------------
def test_dashboard_by_project_shape(h):
    r = requests.get(f"{BASE}/dashboard", headers=h, timeout=30)
    assert r.status_code == 200
    d = r.json()
    # KPI row inputs
    assert "consolidated" in d and "projects" in d["consolidated"]
    assert "team_members" in d
    assert "procurement_pending" in d
    assert "procurement_paid" in d

    by = d.get("by_project", [])
    assert len(by) >= 2
    for p in by:
        assert "project_id" in p and "name" in p
        assert "total_units" in p and "sold" in p
        # pivots exist (may be empty for VV OLD schema)
        assert isinstance(p.get("pivots", []), list)

    # Verify counts match seed
    vv = next(x for x in by if x["project_id"] == VV)
    cvf = next(x for x in by if x["project_id"] == CVF)
    assert vv["total_units"] == 256
    assert cvf["total_units"] == 47


# ---------------- Sell: buyer optional ----------------
def _first_available_cvf_unit(h):
    r = requests.get(f"{BASE}/units", headers=h,
                     params={"project_id": CVF}, timeout=20).json()
    return next(u for u in r if u["status"] == "available")


def test_sell_with_empty_buyer(h):
    unit = _first_available_cvf_unit(h)
    uid = unit["unit_id"]
    plot = unit["plot_number"]

    payload = {
        "buyer_name": "",
        "buyer_contact": "",
        "sale_date": "2026-01-15",
        "final_price": 100000,
        "booking_amount": 10000,
        "schedule": [
            {"due_date": "2026-02-15", "amount": 50000, "notes": "On agreement"},
            {"due_date": "2026-03-15", "amount": 50000, "notes": ""},
        ],
    }
    r = requests.post(f"{BASE}/units/{uid}/sell", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert len(body.get("payments", [])) == 2

    # Confirm unit now sold
    r2 = requests.get(f"{BASE}/units", headers=h,
                      params={"project_id": CVF}).json()
    sold = next(x for x in r2 if x["unit_id"] == uid)
    assert sold["status"] == "sold"
    assert sold.get("buyer_name", "") == ""

    # Also confirm dashboard sold-count reflects the sale (>=1 for CVF)
    d = requests.get(f"{BASE}/dashboard", headers=h).json()
    cvf = next(x for x in d["by_project"] if x["project_id"] == CVF)
    assert cvf["sold"] >= 1

    # ---- CLEANUP: revert unit + delete payments + delete notification ----
    import pymongo
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    dbname = os.environ.get("DB_NAME", "agrocorp_lite")
    mdb = mongo[dbname]
    mdb.units.update_one({"unit_id": uid}, {"$set": {"status": "available"},
                                             "$unset": {"buyer_name": "", "buyer_contact": "",
                                                        "sale_date": "", "final_price": "",
                                                        "booking_amount": "", "sold_by": "",
                                                        "sold_at": ""}})
    mdb.payments.delete_many({"unit_id": uid})
    mdb.notifications.delete_many({"kind": "sale_recorded",
                                    "message": {"$regex": f"Plot {plot}"}})
    mongo.close()

    # Confirm cleanup
    r3 = requests.get(f"{BASE}/units", headers=h,
                      params={"project_id": CVF}).json()
    restored = next(x for x in r3 if x["unit_id"] == uid)
    assert restored["status"] == "available"


def test_sell_requires_schedule(h):
    unit = _first_available_cvf_unit(h)
    r = requests.post(f"{BASE}/units/{unit['unit_id']}/sell", headers=h,
                      json={"buyer_name": "", "buyer_contact": "",
                            "sale_date": "2026-01-15", "final_price": 0,
                            "booking_amount": 0, "schedule": []}, timeout=20)
    assert r.status_code == 400
