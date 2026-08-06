"""E2E backend tests for Agrocorp Lite hitting the public URL."""
import io
import os
import time
import uuid
import pytest
import requests
from openpyxl import Workbook

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api" \
    if os.environ.get("REACT_APP_BACKEND_URL") else None

# Fallback: read frontend/.env
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/") + "/api"
                break

ADMIN_PHONE = "9999999999"
ADMIN_INITIAL = "9999999999"
ADMIN_NEW = "Admin@Verify1"


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _login(phone, pwd):
    return requests.post(f"{BASE}/auth/login", json={"phone": phone, "password": pwd}, timeout=30)


def _reset_and_login(phone, initial, new_pwd):
    r = _login(phone, initial)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["must_reset_password"] is True
    r2 = requests.post(f"{BASE}/auth/change-password", headers=_h(d["access_token"]),
                       json={"current_password": initial, "new_password": new_pwd}, timeout=30)
    assert r2.status_code == 200, r2.text
    d2 = _login(phone, new_pwd).json()
    return d2["access_token"]


state = {}


# ---- smoke ----
def test_00_health():
    r = requests.get(f"{BASE}/health", timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---- auth: initial admin login + forced reset ----
def test_01_admin_initial_login():
    r = _login(ADMIN_PHONE, ADMIN_INITIAL)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["role"] == "admin"
    assert d["user"]["must_reset_password"] is True
    state["admin_first_token"] = d["access_token"]


def test_02_admin_change_password():
    r = requests.post(f"{BASE}/auth/change-password",
                      headers=_h(state["admin_first_token"]),
                      json={"current_password": ADMIN_INITIAL, "new_password": ADMIN_NEW}, timeout=30)
    assert r.status_code == 200, r.text


def test_03_admin_relogin():
    r = _login(ADMIN_PHONE, ADMIN_NEW)
    assert r.status_code == 200
    d = r.json()
    assert d["user"]["must_reset_password"] is False
    state["admin"] = d["access_token"]


def test_04_auth_me():
    r = requests.get(f"{BASE}/auth/me", headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


# ---- projects ----
def test_10_create_project():
    r = requests.post(f"{BASE}/projects", headers=_h(state["admin"]),
                      json={"name": "TEST_Verify Project", "location": "Bangalore"}, timeout=30)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["name"] == "TEST_Verify Project"
    state["project_id"] = p["project_id"]

    r2 = requests.post(f"{BASE}/projects", headers=_h(state["admin"]),
                       json={"name": "TEST_Second", "location": "Chennai"}, timeout=30)
    assert r2.status_code == 200
    state["project_id_2"] = r2.json()["project_id"]


def test_11_list_projects():
    r = requests.get(f"{BASE}/projects", headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    ids = {p["project_id"] for p in r.json()}
    assert state["project_id"] in ids
    assert state["project_id_2"] in ids


# ---- users (admin creates team) ----
def test_20_create_team_members():
    users = [
        {"phone": "9222200001", "name": "TEST Acc", "role": "accounts"},
        {"phone": "9222200002", "name": "TEST PS", "role": "post_sales"},
        {"phone": "9222200003", "name": "TEST SM", "role": "site_manager", "project_id": state["project_id"]},
    ]
    for u in users:
        r = requests.post(f"{BASE}/users", headers=_h(state["admin"]), json=u, timeout=30)
        assert r.status_code == 200, f"{u['role']}: {r.status_code} {r.text}"


def test_21_site_manager_requires_project():
    r = requests.post(f"{BASE}/users", headers=_h(state["admin"]),
                      json={"phone": "9222299999", "name": "Bad SM", "role": "site_manager"}, timeout=30)
    assert r.status_code == 400


def test_22_duplicate_phone():
    r = requests.post(f"{BASE}/users", headers=_h(state["admin"]),
                      json={"phone": "9222200001", "name": "dup", "role": "accounts"}, timeout=30)
    assert r.status_code == 400


# ---- units import via Excel ----
def test_30_units_import_excel():
    # Build an Excel matching the fuzzy header expectations
    wb = Workbook()
    ws = wb.active
    ws.append(["Sheet Title"])
    ws.append(["UNIT NO.", "EXTENT (SFT)", "Basic Sale Price",
               "East Facing PLC", "Hill View PLC", "CORNER PLC",
               "Infrastructure & development charges",
               "Legal and Administrative Charges",
               "Club membership",
               "Advance maintenance Charges for 2 years",
               "IFMS", "Grand Total"])
    ws.append(["A-1", 1200, 5000000, 0, 0, 0, 100000, 25000, 50000, 30000, 20000, 5225000])
    ws.append(["A-2", 1400, 5800000, 100000, 0, 0, 120000, 25000, 50000, 30000, 20000, 6145000])
    ws.append(["A-3", 1100, 4500000, 0, 0, 50000, 90000, 25000, 50000, 30000, 20000, 4765000])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    files = {"file": ("units.xlsx", buf.getvalue(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/units/import", headers=_h(state["admin"]),
                      data={"project_id": state["project_id"]}, files=files, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inserted"] >= 3, body


def test_31_list_units():
    r = requests.get(f"{BASE}/units?project_id=" + state["project_id"],
                     headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    units = r.json()
    assert len(units) >= 3
    a1 = next((u for u in units if u["plot_number"] == "A-1"), None)
    assert a1 and a1["status"] == "available"
    state["unit_id"] = a1["unit_id"]


# ---- post_sales sells the unit ----
def test_40_ps_reset_and_sell():
    ps_token = _reset_and_login("9222200002", "9222200002", "PostSales1!")
    state["ps"] = ps_token

    body = {
        "buyer_name": "TEST Buyer",
        "buyer_contact": "9998887777",
        "sale_date": "2026-02-05",
        "final_price": 6000000,
        "booking_amount": 300000,
        "schedule": [
            {"amount": 1140000, "due_date": "2026-03-05"},
            {"amount": 1140000, "due_date": "2026-04-05"},
            {"amount": 1140000, "due_date": "2026-05-05"},
            {"amount": 1140000, "due_date": "2026-06-05"},
            {"amount": 1140000, "due_date": "2026-07-05"},
        ],
    }
    r = requests.post(f"{BASE}/units/{state['unit_id']}/sell",
                      headers=_h(ps_token), json=body, timeout=30)
    assert r.status_code == 200, r.text
    assert len(r.json()["payments"]) == 5


def test_41_schedule_mismatch_rejected():
    # get another available unit
    r = requests.get(f"{BASE}/units?project_id=" + state["project_id"] + "&status=available",
                     headers=_h(state["admin"]), timeout=15)
    unit = r.json()[0]
    body = {
        "buyer_name": "x", "buyer_contact": "9", "sale_date": "2026-02-05",
        "final_price": 1000000, "booking_amount": 100000,
        "schedule": [{"amount": 500000, "due_date": "2026-03-05"}],  # short by 400k
    }
    r = requests.post(f"{BASE}/units/{unit['unit_id']}/sell",
                      headers=_h(state["ps"]), json=body, timeout=30)
    assert r.status_code == 400


# ---- accounts flow ----
def test_50_accounts_reset_and_notifications():
    acc_token = _reset_and_login("9222200001", "9222200001", "Accounts1!")
    state["acc"] = acc_token
    r = requests.get(f"{BASE}/notifications", headers=_h(acc_token), timeout=15)
    assert r.status_code == 200
    kinds = [n["kind"] for n in r.json()]
    assert "sale_recorded" in kinds


def test_51_accounts_mark_payment_received():
    r = requests.get(f"{BASE}/payments", headers=_h(state["acc"]), timeout=15)
    assert r.status_code == 200
    pays = r.json()
    assert len(pays) >= 5
    pid = pays[0]["payment_id"]
    r = requests.patch(f"{BASE}/payments/{pid}", headers=_h(state["acc"]),
                       json={"status": "received", "received_date": "2026-03-06"}, timeout=30)
    assert r.status_code == 200
    # Verify persistence via GET
    r = requests.get(f"{BASE}/payments?unit_id=" + state["unit_id"],
                     headers=_h(state["acc"]), timeout=15)
    updated = [p for p in r.json() if p["payment_id"] == pid][0]
    assert updated["status"] == "received"
    assert updated["received_date"] == "2026-03-06"


# ---- procurement site_manager -> admin -> accounts ----
def test_60_sm_reset_and_procurement():
    sm_token = _reset_and_login("9222200003", "9222200003", "SiteMgr1!")
    state["sm"] = sm_token

    r = requests.post(f"{BASE}/procurement", headers=_h(sm_token),
                      json={"project_id": state["project_id"], "subject": "TEST Cement + Steel",
                            "priority": "high",
                            "items": [
                                {"name": "Cement", "quantity": 100, "unit": "bag", "est_cost": 40000},
                                {"name": "Steel", "quantity": 500, "unit": "kg", "est_cost": 30000},
                            ]}, timeout=30)
    assert r.status_code == 200, r.text
    state["proc_id"] = r.json()["request_id"]


def test_61_admin_gets_procurement_notification():
    r = requests.get(f"{BASE}/notifications", headers=_h(state["admin"]), timeout=15)
    kinds = [n["kind"] for n in r.json()]
    assert "procurement_new" in kinds


def test_62_admin_clarify_then_approve():
    pid = state["proc_id"]
    r = requests.post(f"{BASE}/procurement/{pid}/action", headers=_h(state["admin"]),
                      json={"action": "clarify", "note": "vendor quote?"}, timeout=30)
    assert r.status_code == 200
    r = requests.post(f"{BASE}/procurement/{pid}/action", headers=_h(state["admin"]),
                      json={"action": "approve", "note": "ok"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_63_accounts_records_procurement_payment():
    pid = state["proc_id"]
    r = requests.post(f"{BASE}/procurement/{pid}/payment", headers=_h(state["acc"]),
                      json={"po_number": "PO-001", "paid_amount": 70000,
                            "paid_date": "2026-02-10"}, timeout=30)
    assert r.status_code == 200
    # verify
    r = requests.get(f"{BASE}/procurement", headers=_h(state["admin"]), timeout=15)
    p = [x for x in r.json() if x["request_id"] == pid][0]
    assert p["status"] == "paid"
    assert p["po_number"] == "PO-001"


# ---- inventory CRUD ----
def test_70_inventory_crud():
    r = requests.post(f"{BASE}/inventory", headers=_h(state["sm"]),
                      json={"project_id": state["project_id"], "name": "TEST Cement",
                            "quantity": 50, "unit": "bag"}, timeout=30)
    assert r.status_code == 200, r.text
    item_id = r.json()["item_id"]

    r = requests.patch(f"{BASE}/inventory/{item_id}", headers=_h(state["sm"]),
                       json={"quantity": 75}, timeout=30)
    assert r.status_code == 200

    r = requests.get(f"{BASE}/inventory", headers=_h(state["sm"]), timeout=15)
    it = [x for x in r.json() if x["item_id"] == item_id][0]
    assert it["quantity"] == 75

    r = requests.delete(f"{BASE}/inventory/{item_id}", headers=_h(state["sm"]), timeout=30)
    assert r.status_code == 200


# ---- notifications ----
def test_80_notifications_mark_read():
    r = requests.get(f"{BASE}/notifications", headers=_h(state["admin"]), timeout=15)
    notifs = r.json()
    assert notifs
    nid = notifs[0]["notification_id"]
    r = requests.post(f"{BASE}/notifications/{nid}/read", headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    r = requests.post(f"{BASE}/notifications/read-all", headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/notifications", headers=_h(state["admin"]), timeout=15)
    assert all(n["is_read"] for n in r.json())


# ---- dashboard ----
def test_90_dashboard():
    r = requests.get(f"{BASE}/dashboard", headers=_h(state["admin"]), timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ["projects", "units_available", "units_sold",
              "payments_pending", "procurement_pending"]:
        assert k in d
    assert d["projects"] >= 2
    assert d["units_sold"] >= 1


# ---- RBAC negatives ----
def test_95_rbac_post_sales_cannot_create_users():
    r = requests.post(f"{BASE}/users", headers=_h(state["ps"]),
                      json={"phone": "9111100000", "name": "x", "role": "accounts"}, timeout=30)
    assert r.status_code == 403


def test_96_rbac_sm_wrong_project():
    r = requests.post(f"{BASE}/procurement", headers=_h(state["sm"]),
                      json={"project_id": state["project_id_2"], "subject": "x",
                            "items": [{"name": "a", "quantity": 1, "unit": "u", "est_cost": 1}]}, timeout=30)
    assert r.status_code == 403


def test_97_rbac_sm_project_scoping():
    r = requests.get(f"{BASE}/projects", headers=_h(state["sm"]), timeout=15)
    ids = {p["project_id"] for p in r.json()}
    assert state["project_id"] in ids
    assert state["project_id_2"] not in ids


def test_98_unauth_users_list():
    r = requests.get(f"{BASE}/users", timeout=15)
    assert r.status_code == 401
