"""E2E verification of Agrocorp Lite after folder relocation to /app/lite/."""
import os
import pytest
import requests
from pymongo import MongoClient

BASE = "http://localhost:8100/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "agrocorp_lite_verify"


@pytest.fixture(scope="session", autouse=True)
def _wipe_and_reprovision():
    """Wipe DB and force backend to reprovision admin before the suite runs."""
    import subprocess, time
    client = MongoClient(MONGO_URL)
    client.drop_database(DB_NAME)
    client.close()
    # Restart the lite backend so seed_admin runs on empty users collection
    subprocess.run(["pkill", "-f", "port 8100"])
    time.sleep(2)
    subprocess.Popen(
        ["/root/.venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"],
        cwd="/app/lite/backend",
        stdout=open("/tmp/lite_backend.log", "w"),
        stderr=subprocess.STDOUT,
    )
    # Wait for health
    for _ in range(30):
        try:
            if requests.get(f"{BASE}/health", timeout=1).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    yield


@pytest.fixture(scope="module")
def state():
    return {}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _login(phone, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"phone": phone, "password": pwd})
    assert r.status_code == 200, r.text
    return r.json()


def _reset_and_login(phone, initial_pwd, new_pwd):
    d = _login(phone, initial_pwd)
    assert d["user"].get("must_reset_password") is True
    r = requests.post(
        f"{BASE}/auth/change-password",
        headers=_h(d["access_token"]),
        json={"current_password": initial_pwd, "new_password": new_pwd},
    )
    assert r.status_code == 200, r.text
    return _login(phone, new_pwd)["access_token"]


# ---- Smoke ----
def test_00_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200 and r.json().get("status") == "ok"


# ---- 1) initial admin login ----
def test_01_initial_admin_login(state):
    r = requests.post(f"{BASE}/auth/login", json={"phone": "9999999999", "password": "9999999999"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["must_reset_password"] is True
    assert d["user"]["role"] == "admin"
    state["admin_first_token"] = d["access_token"]


# ---- 2) change admin password ----
def test_02_change_admin_password(state):
    r = requests.post(
        f"{BASE}/auth/change-password",
        headers=_h(state["admin_first_token"]),
        json={"current_password": "9999999999", "new_password": "Admin@Verify1"},
    )
    assert r.status_code == 200, r.text


# ---- 3) relogin admin ----
def test_03_relogin_admin(state):
    d = _login("9999999999", "Admin@Verify1")
    assert d["user"]["must_reset_password"] is False
    state["admin"] = d["access_token"]


# ---- 4) create project ----
def test_04_create_project(state):
    r = requests.post(f"{BASE}/projects", headers=_h(state["admin"]),
                      json={"name": "Verify Project", "location": "Bangalore"})
    assert r.status_code == 200, r.text
    state["project_id"] = r.json()["project_id"]

    r2 = requests.post(f"{BASE}/projects", headers=_h(state["admin"]),
                       json={"name": "Second Project", "location": "Chennai"})
    assert r2.status_code == 200
    state["project_id_2"] = r2.json()["project_id"]


# ---- 5) create 3 member users ----
def test_05_create_users(state):
    users = [
        {"phone": "9222200001", "name": "Acc User", "role": "accounts"},
        {"phone": "9222200002", "name": "PS User", "role": "post_sales"},
        {"phone": "9222200003", "name": "SM User", "role": "site_manager",
         "project_id": state["project_id"]},
    ]
    for u in users:
        r = requests.post(f"{BASE}/users", headers=_h(state["admin"]), json=u)
        assert r.status_code == 200, f"{u['role']}: {r.status_code} {r.text}"


# ---- create a unit directly in DB (no create-unit endpoint; only Excel import) ----
def test_055_seed_unit(state):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    from datetime import datetime, timezone
    import uuid
    unit_id = f"unit_{uuid.uuid4().hex[:12]}"
    db.units.insert_one({
        "unit_id": unit_id,
        "project_id": state["project_id"],
        "plot_number": "A-1",
        "area_sqft": 1200.0,
        "plc_details": {}, "other_charges": {},
        "status": "available",
        "final_price": 0, "booking_amount": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    state["unit_id"] = unit_id
    client.close()


# ---- 6) post_sales sells the unit ----
def test_06_post_sales_sell_unit(state):
    ps_token = _reset_and_login("9222200002", "9222200002", "PostSales1")
    state["ps"] = ps_token

    body = {
        "buyer_name": "Test Jay",
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
                      headers=_h(ps_token), json=body)
    assert r.status_code == 200, r.text
    payments = r.json().get("payments", [])
    assert len(payments) == 5, f"expected 5 payments, got {len(payments)}"


# ---- 7) accounts sees notification, marks first payment received ----
def test_07_accounts_notification_and_pay(state):
    acc_token = _reset_and_login("9222200001", "9222200001", "Accounts1")
    state["acc"] = acc_token

    r = requests.get(f"{BASE}/notifications", headers=_h(acc_token))
    assert r.status_code == 200, r.text
    notifs = r.json()
    kinds = [n.get("kind") for n in notifs]
    assert "sale_recorded" in kinds, f"expected sale_recorded notification, got {kinds}"

    r = requests.get(f"{BASE}/payments", headers=_h(acc_token))
    assert r.status_code == 200
    pays = r.json()
    assert len(pays) >= 5
    pid = pays[0]["payment_id"]

    r = requests.patch(f"{BASE}/payments/{pid}", headers=_h(acc_token),
                       json={"status": "received", "received_date": "2026-03-06"})
    assert r.status_code == 200, r.text


# ---- 8) site_manager creates procurement ----
def test_08_site_manager_procurement(state):
    sm_token = _reset_and_login("9222200003", "9222200003", "SiteMgr1")
    state["sm"] = sm_token

    body = {
        "project_id": state["project_id"],
        "subject": "Cement + Steel",
        "items": [
            {"name": "Cement", "quantity": 100, "unit": "bag", "est_cost": 40000},
            {"name": "Steel", "quantity": 500, "unit": "kg", "est_cost": 30000},
        ],
    }
    r = requests.post(f"{BASE}/procurement", headers=_h(sm_token), json=body)
    assert r.status_code == 200, r.text
    state["proc_id"] = r.json()["request_id"]


# ---- 9) admin clarifies then approves ----
def test_09_admin_clarify_then_approve(state):
    pid = state["proc_id"]
    r = requests.post(f"{BASE}/procurement/{pid}/action",
                      headers=_h(state["admin"]),
                      json={"action": "clarify", "note": "Please share vendor quote"})
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/procurement/{pid}/action",
                      headers=_h(state["admin"]),
                      json={"action": "approve", "note": "OK"})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "approved"


# ---- 10) accounts records procurement payment ----
def test_10_accounts_records_payment(state):
    pid = state["proc_id"]
    r = requests.post(f"{BASE}/procurement/{pid}/payment",
                      headers=_h(state["acc"]),
                      json={"po_number": "PO-001", "paid_amount": 70000,
                            "paid_date": "2026-02-10"})
    assert r.status_code == 200, r.text


# ---- 11) site_manager creates inventory item ----
def test_11_site_manager_inventory(state):
    r = requests.post(f"{BASE}/inventory", headers=_h(state["sm"]),
                      json={"project_id": state["project_id"],
                            "name": "Cement", "quantity": 100, "unit": "bag"})
    assert r.status_code == 200, r.text


# ---- 12) site_manager sees only assigned project ----
def test_12_site_manager_project_scoping(state):
    r = requests.get(f"{BASE}/projects", headers=_h(state["sm"]))
    assert r.status_code == 200
    ids = {p["project_id"] for p in r.json()}
    assert state["project_id"] in ids
    assert state["project_id_2"] not in ids, \
        f"site_manager should not see other projects: {ids}"


# ---- RBAC negatives ----
def test_rbac_post_sales_cannot_create_users(state):
    r = requests.post(f"{BASE}/users", headers=_h(state["ps"]),
                      json={"phone": "9111100000", "name": "x", "role": "accounts"})
    assert r.status_code == 403, r.status_code


def test_rbac_site_manager_wrong_project(state):
    r = requests.post(f"{BASE}/procurement", headers=_h(state["sm"]),
                      json={"project_id": state["project_id_2"], "subject": "x",
                            "items": [{"name": "a", "quantity": 1, "unit": "u",
                                        "est_cost": 1}]})
    assert r.status_code == 403, r.status_code


def test_rbac_unauthenticated_users_list():
    r = requests.get(f"{BASE}/users")
    assert r.status_code == 401, r.status_code
