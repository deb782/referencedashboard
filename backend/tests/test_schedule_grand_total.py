"""Backend tests for Grand Total / schedule / report Total Payable enforcement."""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://read-start-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "agrocorp_lite"

PROJECT_ID = "proj_01d7e89ba838"  # Central Vista Farms


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


def _login(phone, password):
    r = requests.post(f"{API}/auth/login", json={"phone": phone, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def post_sales_token():
    return _login("9000000001", "Pass@123")


@pytest.fixture(scope="module")
def accounts_token():
    return _login("9000000002", "Pass@123")


@pytest.fixture(scope="module")
def admin_token():
    return _login("9513242807", "Repro@123")


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


@pytest.fixture(scope="module")
def target_unit(db):
    """Pick an available unit in CVF and compute its Grand Total from charge columns."""
    proj = db.projects.find_one({"project_id": PROJECT_ID}, {"_id": 0})
    assert proj, "CVF project not found"
    charge_keys = [c["key"] for c in proj.get("columns", []) if c.get("tag") == "charge"]
    assert charge_keys, "No charge columns on CVF"
    # Find available with grand_total > 0
    u = None
    for cand in db.units.find({"project_id": PROJECT_ID, "status": "available"}, {"_id": 0}):
        gt = round(sum(_num(cand.get("data", {}).get(k)) for k in charge_keys), 2)
        if gt > 0:
            u = cand
            u["_grand_total"] = gt
            break
    assert u, "No available unit with charges in CVF"
    print(f"Using unit_id={u['unit_id']} plot={u['plot_number']} grand_total={u['_grand_total']}")
    yield u
    # Cleanup: reset the unit + delete payments/schedule_logs regardless of test outcome
    db.payments.delete_many({"unit_id": u["unit_id"]})
    db.schedule_logs.delete_many({"unit_id": u["unit_id"]})
    db.units.update_one({"unit_id": u["unit_id"]}, {
        "$set": {"status": "available"},
        "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                   "final_price": "", "booking_amount": "", "sold_by": "", "sold_at": ""}})
    print(f"Cleanup done for {u['unit_id']}")


def _headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------- Sell endpoint checks ----------------

def test_sell_with_wrong_schedule_rejected(post_sales_token, target_unit):
    gt = target_unit["_grand_total"]
    wrong_amt = round(gt - 10000, 2)
    payload = {
        "buyer_name": "TEST_Buyer_Wrong",
        "buyer_contact": "9999999999",
        "sale_date": "2026-01-05",
        "final_price": gt,
        "booking_amount": 100000,
        "schedule": [
            {"due_date": "2026-01-15", "amount": wrong_amt, "notes": "Booking"},
        ],
    }
    r = requests.post(f"{API}/units/{target_unit['unit_id']}/sell",
                      headers=_headers(post_sales_token), json=payload)
    assert r.status_code == 400, r.text
    assert "Grand Total" in r.text, r.text


def test_sell_with_correct_schedule_succeeds(post_sales_token, target_unit):
    gt = target_unit["_grand_total"]
    # Split into 2 instalments summing exactly to GT
    a1 = round(gt / 2, 2)
    a2 = round(gt - a1, 2)
    payload = {
        "buyer_name": "TEST_Buyer_OK",
        "buyer_contact": "9999999999",
        "sale_date": "2026-01-05",
        "final_price": gt,
        "booking_amount": 100000,
        "schedule": [
            {"due_date": "2026-01-15", "amount": a1, "notes": "Booking"},
            {"due_date": "2026-02-15", "amount": a2, "notes": "Final"},
        ],
    }
    r = requests.post(f"{API}/units/{target_unit['unit_id']}/sell",
                      headers=_headers(post_sales_token), json=payload)
    assert r.status_code == 200, r.text


# ---------------- Payment report reflects schedule sum ----------------

def test_payment_report_total_payable_equals_schedule(post_sales_token, target_unit, db):
    """The PDF report's total_payable is _plot_report_data's schedule sum.
    We assert schedule sum in DB equals GT."""
    sched_sum = round(sum(_num(p.get("amount")) for p in
                          db.payments.find({"unit_id": target_unit["unit_id"]})), 2)
    assert abs(sched_sum - target_unit["_grand_total"]) < 1
    # Endpoint returns PDF; assert 200 + PDF magic bytes
    r = requests.get(f"{API}/units/{target_unit['unit_id']}/payment-report",
                     headers=_headers(post_sales_token))
    assert r.status_code == 200, r.text[:400]
    assert r.content[:4] == b"%PDF", "not a PDF"


# ---------------- Edit schedule checks ----------------

def test_edit_schedule_mismatch_rejected(post_sales_token, target_unit, db):
    # Fetch current payments to preserve payment_ids
    pays = list(db.payments.find({"unit_id": target_unit["unit_id"]}, {"_id": 0}).sort("seq", 1))
    assert len(pays) >= 2
    installments = [
        {"payment_id": pays[0]["payment_id"], "due_date": pays[0]["due_date"],
         "amount": round(pays[0]["amount"] - 5000, 2), "notes": pays[0].get("notes", "")},
        {"payment_id": pays[1]["payment_id"], "due_date": pays[1]["due_date"],
         "amount": pays[1]["amount"], "notes": pays[1].get("notes", "")},
    ]
    r = requests.put(f"{API}/units/{target_unit['unit_id']}/schedule",
                     headers=_headers(post_sales_token), json={"installments": installments})
    assert r.status_code == 400, r.text
    assert "Grand Total" in r.text


def test_edit_schedule_matching_succeeds(post_sales_token, target_unit, db):
    gt = target_unit["_grand_total"]
    pays = list(db.payments.find({"unit_id": target_unit["unit_id"]}, {"_id": 0}).sort("seq", 1))
    # Re-split into 3 instalments summing to GT (with new one)
    a1 = round(gt * 0.3, 2)
    a2 = round(gt * 0.3, 2)
    a3 = round(gt - a1 - a2, 2)
    installments = [
        {"payment_id": pays[0]["payment_id"], "due_date": "2026-01-20",
         "amount": a1, "notes": "Booking edited"},
        {"payment_id": pays[1]["payment_id"], "due_date": "2026-02-20",
         "amount": a2, "notes": "Mid"},
        {"due_date": "2026-03-20", "amount": a3, "notes": "Final new"},
    ]
    r = requests.put(f"{API}/units/{target_unit['unit_id']}/schedule",
                     headers=_headers(post_sales_token), json={"installments": installments})
    assert r.status_code == 200, r.text
    # Report Total Payable reflects new sum
    r2 = requests.get(f"{API}/units/{target_unit['unit_id']}/payment-report",
                      headers=_headers(post_sales_token))
    assert r2.status_code == 200
    sched_sum = round(sum(_num(p.get("amount")) for p in
                          db.payments.find({"unit_id": target_unit["unit_id"]})), 2)
    assert abs(sched_sum - gt) < 1


# ---------------- RBAC regression: only post_sales can PUT schedule ----------------

def test_edit_schedule_forbidden_for_accounts(accounts_token, target_unit, db):
    pays = list(db.payments.find({"unit_id": target_unit["unit_id"]}, {"_id": 0}).sort("seq", 1))
    installments = [{"payment_id": p["payment_id"], "due_date": p["due_date"],
                     "amount": p["amount"], "notes": p.get("notes", "")} for p in pays]
    r = requests.put(f"{API}/units/{target_unit['unit_id']}/schedule",
                     headers=_headers(accounts_token), json={"installments": installments})
    assert r.status_code == 403, r.text


def test_edit_schedule_forbidden_for_admin(admin_token, target_unit, db):
    pays = list(db.payments.find({"unit_id": target_unit["unit_id"]}, {"_id": 0}).sort("seq", 1))
    installments = [{"payment_id": p["payment_id"], "due_date": p["due_date"],
                     "amount": p["amount"], "notes": p.get("notes", "")} for p in pays]
    r = requests.put(f"{API}/units/{target_unit['unit_id']}/schedule",
                     headers=_headers(admin_token), json={"installments": installments})
    assert r.status_code == 403, r.text
