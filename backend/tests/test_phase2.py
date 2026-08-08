"""Phase 2 backend tests — partial payments, /accounts/overview, sell schedule relaxation."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback for backend-side envs
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

CVF_PROJECT_ID = "proj_01d7e89ba838"
ADMIN_PHONE = "9513242807"
ADMIN_PW = "Repro@123"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def cvf_available_unit(admin_client):
    """Pick one available CVF plot; revert after."""
    r = admin_client.get(f"{BASE_URL}/api/units", params={"project_id": CVF_PROJECT_ID, "status": "available"})
    assert r.status_code == 200
    rows = r.json()
    assert rows, "no available CVF plot for testing"
    unit = rows[0]
    yield unit
    # cleanup: revert to available
    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mc[os.environ.get("DB_NAME", "agrocorp_lite")]
    db.units.update_one(
        {"unit_id": unit["unit_id"]},
        {"$set": {"status": "available"},
         "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                    "final_price": "", "booking_amount": "",
                    "sold_by": "", "sold_at": ""}})
    db.payments.delete_many({"unit_id": unit["unit_id"]})
    mc.close()


# --- Sell schedule no longer must equal net-payable ---------------------
def test_sell_with_schedule_not_equal_net_payable(admin_client, cvf_available_unit):
    unit = cvf_available_unit
    payload = {
        "buyer_name": "TEST_PhaseTwo Buyer",
        "buyer_contact": "9990000001",
        "sale_date": "2026-01-15",
        "final_price": 1000000.0,          # net payable 10L
        "booking_amount": 100000.0,
        "schedule": [
            # deliberately does NOT sum to final_price
            {"due_date": "2026-02-15", "amount": 400000.0, "notes": "Instalment 1 · Foundation"},
            {"due_date": "On Offer of Possession", "amount": 200000.0, "notes": "Instalment 2 · Possession"},
        ],
    }
    r = admin_client.post(f"{BASE_URL}/api/units/{unit['unit_id']}/sell", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert len(data["payments"]) == 2
    # verify installment names + possession string preserved
    p1, p2 = sorted(data["payments"], key=lambda x: x["seq"])
    assert p1["notes"] == "Instalment 1 · Foundation"
    assert p2["due_date"] == "On Offer of Possession"
    assert p1["status"] == "pending"
    assert p1["paid_amount"] == 0


# --- Partial payment flow -----------------------------------------------
def test_partial_then_full_receipt(admin_client, cvf_available_unit):
    unit = cvf_available_unit
    r = admin_client.get(f"{BASE_URL}/api/payments", params={"unit_id": unit["unit_id"]})
    assert r.status_code == 200
    pays = sorted(r.json(), key=lambda x: x["seq"])
    assert len(pays) >= 1
    p1 = pays[0]
    amt = round(float(p1["amount"]), 2)     # 400000
    half = round(amt / 2, 2)

    # first receipt: half
    r1 = admin_client.post(
        f"{BASE_URL}/api/payments/{p1['payment_id']}/receipt",
        json={"amount": half, "notes": "TEST_first-half"})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["status"] == "partial"
    assert d1["paid_amount"] == half

    # GET to verify persistence
    r = admin_client.get(f"{BASE_URL}/api/payments", params={"unit_id": unit["unit_id"]})
    p1_after = [x for x in r.json() if x["payment_id"] == p1["payment_id"]][0]
    assert p1_after["status"] == "partial"
    assert p1_after["paid_amount"] == half
    assert len(p1_after["receipts"]) == 1
    assert p1_after["receipts"][0]["amount"] == half
    assert p1_after["receipts"][0]["notes"] == "TEST_first-half"

    # second receipt: remaining
    remaining = round(amt - half, 2)
    r2 = admin_client.post(
        f"{BASE_URL}/api/payments/{p1['payment_id']}/receipt",
        json={"amount": remaining, "notes": "TEST_second-half"})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["status"] == "received"
    assert abs(d2["paid_amount"] - amt) < 0.01

    # verify receipts array accumulated
    r = admin_client.get(f"{BASE_URL}/api/payments", params={"unit_id": unit["unit_id"]})
    p1_final = [x for x in r.json() if x["payment_id"] == p1["payment_id"]][0]
    assert p1_final["status"] == "received"
    assert len(p1_final["receipts"]) == 2


def test_zero_and_negative_receipt_rejected(admin_client, cvf_available_unit):
    r = admin_client.get(f"{BASE_URL}/api/payments", params={"unit_id": cvf_available_unit["unit_id"]})
    p2 = sorted(r.json(), key=lambda x: x["seq"])[1]
    r0 = admin_client.post(f"{BASE_URL}/api/payments/{p2['payment_id']}/receipt", json={"amount": 0})
    assert r0.status_code == 400
    rn = admin_client.post(f"{BASE_URL}/api/payments/{p2['payment_id']}/receipt", json={"amount": -100})
    assert rn.status_code == 400


# --- /accounts/overview -------------------------------------------------
def test_accounts_overview_structure_and_math(admin_client, cvf_available_unit):
    r = admin_client.get(f"{BASE_URL}/api/accounts/overview")
    assert r.status_code == 200, r.text
    ov = r.json()
    assert "plots" in ov and "site" in ov
    assert "projects" in ov["plots"] and "totals" in ov["plots"]
    assert "rows" in ov["site"] and "pending_total" in ov["site"] and "paid_total" in ov["site"]

    # find our sold plot
    unit = cvf_available_unit
    found_plot = None
    found_proj = None
    for proj in ov["plots"]["projects"]:
        for p in proj["plots"]:
            if p["unit_id"] == unit["unit_id"]:
                found_plot = p
                found_proj = proj
    assert found_plot is not None, "sold test plot missing from overview"
    assert found_proj["name"] == "Central Vista Farms"
    assert found_plot["installments"] == 2
    assert found_plot["total"] == 600000.0  # 400k + 200k
    # After the partial-then-full test we've paid all of instalment 1 = 400k
    assert found_plot["paid"] == 400000.0
    assert found_plot["pending"] == 200000.0
    assert found_plot["buyer_name"] == "TEST_PhaseTwo Buyer"

    # totals sanity
    t = ov["plots"]["totals"]
    assert t["total"] >= found_plot["total"]
    assert round(t["total"] - t["paid"], 2) == t["pending"]
