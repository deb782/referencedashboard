"""Phase 3 backend tests — procurement lifecycle, file uploads, milestones, accounts/overview site head."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")

CVF = "proj_01d7e89ba838"
ADMIN_PHONE = "9513242807"
ADMIN_PW = "Repro@123"


def _pdf_bytes(text="hello"):
    # minimal valid-looking pdf; not a real pdf but content-type is what matters for our test
    return (b"%PDF-1.4\n%TEST\n" + text.encode() + b"\n%%EOF")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": ADMIN_PHONE, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def created(admin_headers):
    """Create a procurement request with a PI file. Yields the response and cleans up."""
    files = {"file": ("pi_test.pdf", _pdf_bytes("pi"), "application/pdf")}
    data = {
        "project_id": CVF,
        "subject": "TEST_Phase3 Cement + Steel",
        "items": '[{"name":"Cement","quantity":10,"unit":"bag","est_cost":400},'
                 '{"name":"Steel","quantity":2,"unit":"ton","est_cost":60000}]',
        "priority": "high",
        "notes": "TEST_phase3",
    }
    r = requests.post(f"{BASE_URL}/api/procurement", data=data, files=files,
                      headers=admin_headers)
    assert r.status_code == 200, r.text
    doc = r.json()
    yield doc

    # cleanup: delete procurement + associated files (best effort)
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = mc[os.environ.get("DB_NAME", "agrocorp_lite")]
        req = db.procurement.find_one({"request_id": doc["request_id"]}) or {}
        for key in ("pi_file", "po_file"):
            f = req.get(key) or {}
            if f.get("file_id"):
                db.files.delete_one({"file_id": f["file_id"]})
        db.procurement.delete_one({"request_id": doc["request_id"]})
        mc.close()
    except Exception:
        pass


# ---------- Lifecycle: create -> approve -> po -> milestones -> pay ----
def test_create_procurement_with_pi(created):
    assert created["status"] == "pending_admin"
    assert created["pi_file"] and created["pi_file"].get("file_id")
    assert created["subject"].startswith("TEST_Phase3")
    assert len(created["items"]) == 2


def test_approve(admin_headers, created):
    r = requests.post(f"{BASE_URL}/api/procurement/{created['request_id']}/action",
                      json={"action": "approve"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_issue_po(admin_headers, created):
    files = {"file": ("po_test.pdf", _pdf_bytes("po"), "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/procurement/{created['request_id']}/po",
                      data={"po_number": "TEST-PO-9001"}, files=files,
                      headers=admin_headers)
    assert r.status_code == 200, r.text
    # verify
    lst = requests.get(f"{BASE_URL}/api/procurement", headers=admin_headers).json()
    doc = next(x for x in lst if x["request_id"] == created["request_id"])
    assert doc["status"] == "po_issued"
    assert doc["po_number"] == "TEST-PO-9001"
    assert doc["po_file"] and doc["po_file"].get("file_id")
    created["po_file"] = doc["po_file"]  # stash for download test


def test_set_milestones(admin_headers, created):
    payload = {"milestones": [
        {"label": "50% advance", "amount": 50000, "due": "2026-02-01"},
        {"label": "50% completion", "amount": 50000, "due": "2026-04-01"},
    ]}
    r = requests.post(f"{BASE_URL}/api/procurement/{created['request_id']}/milestones",
                      json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    ms = r.json()["milestones"]
    assert len(ms) == 2
    assert ms[0]["status"] == "pending"


def test_pay_first_milestone_partial(admin_headers, created):
    r = requests.post(
        f"{BASE_URL}/api/procurement/{created['request_id']}/milestones/0/pay",
        json={"paid_date": "2026-02-05", "notes": "TEST_advance"},
        headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["all_paid"] is False
    assert body["paid_amount"] == 50000
    # status should NOT be 'paid' yet
    lst = requests.get(f"{BASE_URL}/api/procurement", headers=admin_headers).json()
    doc = next(x for x in lst if x["request_id"] == created["request_id"])
    assert doc["status"] == "po_issued"


def test_pay_final_milestone_completes(admin_headers, created):
    r = requests.post(
        f"{BASE_URL}/api/procurement/{created['request_id']}/milestones/1/pay",
        json={"paid_date": "2026-04-05"}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["all_paid"] is True
    assert body["paid_amount"] == 100000
    lst = requests.get(f"{BASE_URL}/api/procurement", headers=admin_headers).json()
    doc = next(x for x in lst if x["request_id"] == created["request_id"])
    assert doc["status"] == "paid"
    assert doc["paid_amount"] == 100000


# ---------- File download & security -----------------------------------
def test_download_pi_with_token(admin_token, created):
    fid = created["pi_file"]["file_id"]
    r = requests.get(f"{BASE_URL}/api/files/{fid}/download",
                     params={"token": admin_token})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")


def test_download_missing_token(created):
    fid = created["pi_file"]["file_id"]
    r = requests.get(f"{BASE_URL}/api/files/{fid}/download")
    assert r.status_code == 401


def test_download_bad_token(created):
    fid = created["pi_file"]["file_id"]
    r = requests.get(f"{BASE_URL}/api/files/{fid}/download",
                     params={"token": "not.a.valid.jwt"})
    assert r.status_code == 401


def test_download_unknown_file(admin_token):
    r = requests.get(f"{BASE_URL}/api/files/file_doesnotexist/download",
                     params={"token": admin_token})
    assert r.status_code == 404


def test_download_via_bearer_header(admin_headers, created):
    fid = created["pi_file"]["file_id"]
    r = requests.get(f"{BASE_URL}/api/files/{fid}/download", headers=admin_headers)
    assert r.status_code == 200


# ---------- Accounts overview site head --------------------------------
def test_accounts_overview_site_head(admin_headers, created):
    r = requests.get(f"{BASE_URL}/api/accounts/overview", headers=admin_headers)
    assert r.status_code == 200, r.text
    site = r.json()["site"]
    row = next((x for x in site["rows"] if x["request_id"] == created["request_id"]), None)
    assert row is not None
    assert row["est_total"] == 100000
    assert row["paid"] == 100000
    assert row["pending"] == 0
    assert row["status"] == "paid"
    assert row["po_number"] == "TEST-PO-9001"
    assert len(row["milestones"]) == 2
    # aggregates include this row
    assert site["paid_total"] >= 100000


# ---------- Admin dashboard site_bills ---------------------------------
def test_admin_dashboard_site_bills(admin_headers, created):
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=admin_headers)
    assert r.status_code == 200, r.text
    sb = r.json().get("site_bills")
    assert sb is not None
    assert "pending" in sb and "paid" in sb and "milestones" in sb
    assert sb["paid"] >= 100000
    # at least one milestone from our request appears (list is capped at 8)
    labels = [m.get("label") for m in sb["milestones"]]
    assert any("advance" in (l or "").lower() or "completion" in (l or "").lower() for l in labels)


# ---------- Role scoping quick check -----------------------------------
def test_action_requires_admin_actionable_state(admin_headers, created):
    # Cannot re-approve an already-paid request
    r = requests.post(f"{BASE_URL}/api/procurement/{created['request_id']}/action",
                      json={"action": "approve"}, headers=admin_headers)
    assert r.status_code == 400


def test_create_procurement_bad_items(admin_headers):
    r = requests.post(f"{BASE_URL}/api/procurement",
                      data={"project_id": CVF, "subject": "TEST_bad",
                            "items": "not-json", "priority": "low"},
                      headers=admin_headers)
    assert r.status_code == 400


def test_create_procurement_empty_items(admin_headers):
    r = requests.post(f"{BASE_URL}/api/procurement",
                      data={"project_id": CVF, "subject": "TEST_bad",
                            "items": "[]", "priority": "low"},
                      headers=admin_headers)
    assert r.status_code == 400
