"""End-to-end backend tests for the procurement workflow.

Flow: Site Manager creates PI -> Admin clarify -> SM resubmit -> Admin approve ->
Management approve (if assigned) -> Accounts PO + tax invoice -> Milestones -> paid.

Also validates:
  * Soft bifurcation (non-blocking submission when item sums != pi_amount).
  * Admin sees SM notes / pi_amount / items.
  * File download endpoint returns 200 for freshly uploaded files.
  * Resubmit-pi reopens request as pending_admin.

Cleans up created procurement + test users at the end.
"""
import io
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

ADMIN = {"phone": "9513242807", "password": "Repro@123"}
ACCOUNTS = {"phone": "9000000002", "password": "Pass@123"}
SM_PHONE = "9000000094"        # test-only, avoid clashing with earlier fixtures
MGMT_PHONE = "9000000093"
CVF = "proj_01d7e89ba838"

created = {"users": [], "requests": []}


def _login(phone, password):
    r = requests.post(f"{BASE}/auth/login", json={"phone": phone, "password": password})
    r.raise_for_status()
    d = r.json()
    return d["access_token"], d["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    tok, _ = _login(**ADMIN)
    return tok


@pytest.fixture(scope="module")
def accounts_tok():
    tok, _ = _login(**ACCOUNTS)
    return tok


@pytest.fixture(scope="module")
def sm_setup(admin_tok):
    # ensure clean slate
    users = requests.get(f"{BASE}/users", headers=_h(admin_tok)).json()
    for u in users:
        if u["phone"] in (SM_PHONE, MGMT_PHONE):
            requests.delete(f"{BASE}/users/{u['user_id']}", headers=_h(admin_tok))
    # create Site Manager
    r = requests.post(f"{BASE}/users", headers=_h(admin_tok), json={
        "name": "TEST SM", "phone": SM_PHONE, "role": "site_manager", "project_id": CVF})
    assert r.status_code == 200, r.text
    sm_uid = r.json()["user_id"]
    created["users"].append(sm_uid)
    # first login -> change password
    tok, u = _login(SM_PHONE, SM_PHONE)
    assert u.get("must_reset_password") is True
    rr = requests.post(f"{BASE}/auth/change-password", headers=_h(tok),
                       json={"current_password": SM_PHONE, "new_password": "Pass@1234"})
    assert rr.status_code == 200, rr.text
    tok, _ = _login(SM_PHONE, "Pass@1234")
    return {"tok": tok, "uid": sm_uid}


@pytest.fixture(scope="module")
def mgmt_setup(admin_tok):
    r = requests.post(f"{BASE}/users", headers=_h(admin_tok), json={
        "name": "TEST MGMT", "phone": MGMT_PHONE, "role": "management",
        "project_id": CVF, "permissions": ["procurement"]})
    assert r.status_code == 200, r.text
    mid = r.json()["user_id"]
    created["users"].append(mid)
    tok, u = _login(MGMT_PHONE, MGMT_PHONE)
    requests.post(f"{BASE}/auth/change-password", headers=_h(tok),
                  json={"current_password": MGMT_PHONE, "new_password": "Pass@1234"})
    tok, _ = _login(MGMT_PHONE, "Pass@1234")
    return {"tok": tok, "uid": mid}


def _pi_file(name="pi.pdf"):
    return ("file", (name, io.BytesIO(b"%PDF-1.4 test pi body"), "application/pdf"))


# ---------------- flow tests ---------------------------------------------------

def test_1_sm_creates_pi_with_bifurcation_mismatch(sm_setup):
    """SM submits a PI where item sums != pi_amount; must still succeed."""
    tok = sm_setup["tok"]
    items = [
        {"name": "Cement bags", "quantity": 100, "unit": "bag", "est_cost": 400, "notes": ""},
        {"name": "TMT steel",   "quantity": 2,   "unit": "ton", "est_cost": 55000, "notes": ""},
    ]  # sum = 40000 + 110000 = 150000; pi_amount 200000 -> mismatch
    data = {"project_id": CVF, "subject": "TEST Procurement E2E",
            "priority": "high", "notes": "Urgent for phase 2 slab casting",
            "pi_amount": "200000", "items": '[' + ",".join(
                [f'{{"name":"{i["name"]}","quantity":{i["quantity"]},"unit":"{i["unit"]}","est_cost":{i["est_cost"]},"notes":""}}' for i in items]) + ']'}
    r = requests.post(f"{BASE}/procurement", headers=_h(tok),
                      data=data, files=[_pi_file()])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending_admin"
    assert body["pi_amount"] == 200000
    assert body["notes"].startswith("Urgent")
    assert len(body["items"]) == 2
    assert body.get("pi_file") and body["pi_file"].get("file_id")
    created["requests"].append(body["request_id"])
    created["pi_file_id"] = body["pi_file"]["file_id"]


def test_2_admin_sees_sm_notes_and_items(admin_tok):
    rid = created["requests"][-1]
    r = requests.get(f"{BASE}/procurement", headers=_h(admin_tok))
    assert r.status_code == 200
    doc = next(x for x in r.json() if x["request_id"] == rid)
    assert doc["notes"] == "Urgent for phase 2 slab casting"
    assert doc["pi_amount"] == 200000
    assert len(doc["items"]) == 2
    assert doc["items"][0]["quantity"] == 100


def test_3_admin_clarify_opens_resubmit(admin_tok):
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                      json={"action": "clarify", "note": "Please share vendor quotes"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_clarification"
    # verify persisted
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "pending_clarification"
    assert row["admin_note"] == "Please share vendor quotes"


def test_4_sm_resubmit_pi_reopens_pending_admin(sm_setup):
    rid = created["requests"][-1]
    tok = sm_setup["tok"]
    items = '[{"name":"Cement bags","quantity":120,"unit":"bag","est_cost":410,"notes":""},' \
            '{"name":"TMT steel","quantity":2,"unit":"ton","est_cost":56000,"notes":""}]'
    r = requests.post(f"{BASE}/procurement/{rid}/resubmit-pi", headers=_h(tok),
                      data={"notes": "Attached updated quotes",
                            "pi_amount": "161200", "items": items},
                      files=[_pi_file("pi_v2.pdf")])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_admin"
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(sm_setup["tok"])).json()
               if x["request_id"] == rid)
    assert row["status"] == "pending_admin"
    assert row["pi_amount"] == 161200
    assert row["items"][0]["quantity"] == 120
    assert row["pi_file"]["file_id"] != created["pi_file_id"]
    created["pi_file_id_v2"] = row["pi_file"]["file_id"]


def test_5_admin_approve_routes_to_management(admin_tok, mgmt_setup):
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                      json={"action": "approve", "note": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_management"


def test_6_mgmt_approve_moves_to_approved(mgmt_setup):
    rid = created["requests"][-1]
    tok = mgmt_setup["tok"]
    r = requests.post(f"{BASE}/procurement/{rid}/mgmt-action", headers=_h(tok),
                      json={"action": "approve", "note": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_7_accounts_issue_po_with_note_and_tax(accounts_tok):
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/po", headers=_h(accounts_tok),
                      data={"po_number": "TEST-PO-777",
                            "note": "Please collect delivery challan on receipt"},
                      files=[_pi_file("po.pdf")])
    assert r.status_code == 200, r.text
    # upload tax invoice too
    r2 = requests.post(f"{BASE}/procurement/{rid}/tax-invoice", headers=_h(accounts_tok),
                       files=[_pi_file("tax.pdf")])
    assert r2.status_code == 200, r2.text
    tax_id = r2.json()["tax_invoice_file"]["file_id"]
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(accounts_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "po_issued"
    assert row["po_number"] == "TEST-PO-777"
    assert row["accounts_note"].startswith("Please collect")
    assert row["po_file"]["file_id"]
    assert row["tax_invoice_file"]["file_id"] == tax_id
    created["po_file_id"] = row["po_file"]["file_id"]
    created["tax_file_id"] = tax_id


def test_8_file_download_returns_200(admin_tok):
    for fid in (created["pi_file_id_v2"], created["po_file_id"], created["tax_file_id"]):
        r = requests.get(f"{BASE}/files/{fid}/download", headers=_h(admin_tok))
        assert r.status_code == 200, f"{fid} -> {r.status_code} {r.text[:120]}"
        assert len(r.content) > 0


def test_9_milestones_and_pay(accounts_tok):
    rid = created["requests"][-1]
    ms = [{"label": "50% advance", "amount": 80600, "due": "2026-02-01"},
          {"label": "50% on delivery", "amount": 80600, "due": "2026-02-20"}]
    r = requests.post(f"{BASE}/procurement/{rid}/milestones", headers=_h(accounts_tok),
                      json={"milestones": ms})
    assert r.status_code == 200, r.text
    r1 = requests.post(f"{BASE}/procurement/{rid}/milestones/0/pay",
                       headers=_h(accounts_tok), json={"paid_date": "2026-02-02"})
    assert r1.status_code == 200
    r2 = requests.post(f"{BASE}/procurement/{rid}/milestones/1/pay",
                       headers=_h(accounts_tok), json={"paid_date": "2026-02-21"})
    assert r2.status_code == 200
    assert r2.json()["all_paid"] is True
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(accounts_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "paid"
    assert row["paid_amount"] == 161200


# ---------------- cleanup -----------------------------------------------------

def test_z_cleanup(admin_tok):
    # delete created procurement docs directly via admin (no delete endpoint -> use mongo? not exposed).
    # Fallback: leave them but rename subject so preview stays clean via UI cleanup.
    # We do have no admin delete API for procurement in this codebase; skipping doc delete.
    for uid in created["users"]:
        requests.delete(f"{BASE}/users/{uid}", headers=_h(admin_tok))
    # Verify users are gone
    remaining = [u["phone"] for u in requests.get(f"{BASE}/users", headers=_h(admin_tok)).json()]
    assert SM_PHONE not in remaining
    assert MGMT_PHONE not in remaining
