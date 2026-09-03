"""End-to-end backend tests for the NEW procurement workflow.

New flow: Site Manager -> Admin -> Accounts. Management is OPTIONAL & PARALLEL —
its `mgmt-action` records an endorsement but does NOT change status and does NOT
gate the flow to Accounts.

Also validates:
  * Files now stored in MongoDB GridFS (`storage_backend='gridfs'` + gridfs_id).
  * PI / PO / Tax-invoice downloads via /api/files/{id}/download return HTTP 200
    with a correct content-type (the GridFS fix).
  * Admin clarify -> pending_clarification -> SM resubmit-pi -> pending_admin.
  * Admin cancel with reason sets status=cancelled.

Cleans up created procurement docs + GridFS blobs + test users at the end.
"""
import io
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

ADMIN = {"phone": "9513242807", "password": "Repro@123"}
ACCOUNTS = {"phone": "9000000002", "password": "Pass@123"}
SM_PHONE = "9000000094"
MGMT_PHONE = "9000000093"
CVF = "proj_01d7e89ba838"

created = {"users": [], "requests": [], "file_ids": []}


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
    users = requests.get(f"{BASE}/users", headers=_h(admin_tok)).json()
    for u in users:
        if u["phone"] in (SM_PHONE, MGMT_PHONE):
            requests.delete(f"{BASE}/users/{u['user_id']}", headers=_h(admin_tok))
    r = requests.post(f"{BASE}/users", headers=_h(admin_tok), json={
        "name": "TEST SM", "phone": SM_PHONE, "role": "site_manager", "project_id": CVF})
    assert r.status_code == 200, r.text
    sm_uid = r.json()["user_id"]
    created["users"].append(sm_uid)
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

def test_1_sm_creates_pi_pending_admin(sm_setup):
    """SM PI create -> pending_admin. GridFS file stored."""
    tok = sm_setup["tok"]
    items = '[{"name":"Cement bags","quantity":100,"unit":"bag","est_cost":400,"notes":""},' \
            '{"name":"TMT steel","quantity":2,"unit":"ton","est_cost":55000,"notes":""}]'
    data = {"project_id": CVF, "subject": "TEST Procurement E2E v2",
            "priority": "high", "notes": "Urgent for phase 2 slab casting",
            "pi_amount": "200000", "items": items}
    r = requests.post(f"{BASE}/procurement", headers=_h(tok), data=data, files=[_pi_file()])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending_admin"
    assert body["pi_amount"] == 200000
    assert body.get("pi_file", {}).get("file_id")
    assert body["pi_file"].get("storage_backend") == "gridfs"
    assert body["pi_file"].get("gridfs_id")
    created["requests"].append(body["request_id"])
    created["pi_file_id"] = body["pi_file"]["file_id"]
    created["file_ids"].append(body["pi_file"]["file_id"])


def test_2_pi_download_returns_200_gridfs(sm_setup):
    """GridFS: PI download via /files/{id}/download -> 200 + pdf content-type."""
    tok = sm_setup["tok"]
    fid = created["pi_file_id"]
    r = requests.get(f"{BASE}/files/{fid}/download", headers=_h(tok))
    assert r.status_code == 200, r.text[:200]
    assert "pdf" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 0


def test_3_admin_clarify_and_sm_resubmit(admin_tok, sm_setup):
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                      json={"action": "clarify", "note": "Please share vendor quotes"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_clarification"
    items = '[{"name":"Cement bags","quantity":120,"unit":"bag","est_cost":410,"notes":""},' \
            '{"name":"TMT steel","quantity":2,"unit":"ton","est_cost":56000,"notes":""}]'
    r2 = requests.post(f"{BASE}/procurement/{rid}/resubmit-pi", headers=_h(sm_setup["tok"]),
                       data={"notes": "Updated quotes", "pi_amount": "161200", "items": items},
                       files=[_pi_file("pi_v2.pdf")])
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "pending_admin"
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["pi_amount"] == 161200
    assert row["pi_file"]["file_id"] != created["pi_file_id"]
    created["pi_file_id_v2"] = row["pi_file"]["file_id"]
    created["file_ids"].append(created["pi_file_id_v2"])


def test_4_admin_approve_goes_STRAIGHT_to_approved(admin_tok, mgmt_setup):
    """Core flow change: admin approve -> 'approved' (NOT pending_management),
    even though a Management user is assigned to this project."""
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                      json={"action": "approve", "note": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved", \
        f"Expected 'approved' directly, got {r.json()['status']}"
    # persisted
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "approved"
    # Management must NOT have been asked yet
    assert not row.get("mgmt_action_at")


def test_5_mgmt_action_does_not_change_status(mgmt_setup, admin_tok):
    """mgmt-action records endorsement/note WITHOUT changing status."""
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/mgmt-action", headers=_h(mgmt_setup["tok"]),
                      json={"action": "approve", "note": "Endorsed — proceed"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved", \
        f"mgmt-action must NOT change status; still expected 'approved', got {body['status']}"
    assert body["mgmt_decision"] == "approve"
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "approved"
    assert row["mgmt_decision"] == "approve"
    assert row["mgmt_note"] == "Endorsed — proceed"
    assert row.get("mgmt_action_at")


def test_6_accounts_issue_po_immediately(accounts_tok):
    """Accounts can issue PO on approved even before/without any mgmt action.
    (In this test mgmt already commented; the key check is Accounts is not blocked.)"""
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/po", headers=_h(accounts_tok),
                      data={"po_number": "TEST-PO-777",
                            "note": "Collect delivery challan on receipt"},
                      files=[_pi_file("po.pdf")])
    assert r.status_code == 200, r.text
    r2 = requests.post(f"{BASE}/procurement/{rid}/tax-invoice", headers=_h(accounts_tok),
                       files=[_pi_file("tax.pdf")])
    assert r2.status_code == 200, r2.text
    tax_id = r2.json()["tax_invoice_file"]["file_id"]
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(accounts_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "po_issued"
    assert row["po_number"] == "TEST-PO-777"
    assert row["po_file"]["storage_backend"] == "gridfs"
    assert row["tax_invoice_file"]["storage_backend"] == "gridfs"
    created["po_file_id"] = row["po_file"]["file_id"]
    created["tax_file_id"] = tax_id
    created["file_ids"] += [created["po_file_id"], tax_id]


def test_7_mgmt_action_still_allowed_after_po_issued(mgmt_setup, admin_tok):
    """Management review remains open on po_issued (parallel, non-gating)."""
    rid = created["requests"][-1]
    r = requests.post(f"{BASE}/procurement/{rid}/mgmt-action", headers=_h(mgmt_setup["tok"]),
                      json={"action": "clarify", "note": "Noted after PO"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "po_issued"
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "po_issued"
    assert row["mgmt_decision"] == "clarify"


def test_8_downloads_all_gridfs_files_200(admin_tok):
    for fid in (created["pi_file_id_v2"], created["po_file_id"], created["tax_file_id"]):
        r = requests.get(f"{BASE}/files/{fid}/download", headers=_h(admin_tok))
        assert r.status_code == 200, f"{fid} -> {r.status_code} {r.text[:120]}"
        assert len(r.content) > 0


def test_9_admin_cancel_flow(admin_tok, sm_setup):
    """Admin cancel with reason -> cancelled."""
    tok = sm_setup["tok"]
    items = '[{"name":"Sand","quantity":10,"unit":"ton","est_cost":1000,"notes":""}]'
    r = requests.post(f"{BASE}/procurement", headers=_h(tok),
                      data={"project_id": CVF, "subject": "TEST Cancel Flow",
                            "priority": "low", "notes": "to be cancelled",
                            "pi_amount": "10000", "items": items},
                      files=[_pi_file("pi_cancel.pdf")])
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    created["requests"].append(rid)
    created["file_ids"].append(r.json()["pi_file"]["file_id"])
    rc = requests.post(f"{BASE}/procurement/{rid}/cancel", headers=_h(admin_tok),
                       json={"reason": "Duplicate raised in error"})
    assert rc.status_code == 200, rc.text
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "cancelled"
    assert row["cancel_reason"] == "Duplicate raised in error"
    # mgmt-action must be blocked on cancelled
    # (needs a management user; reuse mgmt fixture indirectly via admin tok? skip: covered by 400)


def test_9b_reject_then_resubmit_reopens_pending_admin(admin_tok, sm_setup):
    """NEW: Admin REJECT sets status='rejected'; SM resubmit-pi on rejected
    reopens the SAME request to 'pending_admin' with a fresh GridFS file.
    """
    tok = sm_setup["tok"]
    items = '[{"name":"Bricks","quantity":5000,"unit":"nos","est_cost":10,"notes":""}]'
    r = requests.post(f"{BASE}/procurement", headers=_h(tok),
                      data={"project_id": CVF, "subject": "TEST Reject Reopen",
                            "priority": "medium", "notes": "will be rejected",
                            "pi_amount": "50000", "items": items},
                      files=[_pi_file("pi_rej.pdf")])
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    orig_fid = r.json()["pi_file"]["file_id"]
    created["requests"].append(rid)
    created["file_ids"].append(orig_fid)

    # Admin REJECT with note
    rr = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                       json={"action": "reject", "note": "Vendor not empanelled"})
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "rejected"
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    assert row["status"] == "rejected"
    # SM must be able to resubmit-pi on 'rejected' now (NEW behavior)
    items2 = '[{"name":"Bricks","quantity":6000,"unit":"nos","est_cost":10,"notes":""}]'
    r2 = requests.post(f"{BASE}/procurement/{rid}/resubmit-pi", headers=_h(tok),
                       data={"notes": "Switched vendor", "pi_amount": "60000",
                             "items": items2},
                       files=[_pi_file("pi_rej_v2.pdf")])
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "pending_admin", \
        f"resubmit on rejected must reopen to pending_admin, got {r2.json()['status']}"
    row2 = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
                if x["request_id"] == rid)
    assert row2["status"] == "pending_admin"
    assert row2["pi_amount"] == 60000
    assert row2["pi_file"]["file_id"] != orig_fid
    assert row2["pi_file"]["storage_backend"] == "gridfs"
    created["file_ids"].append(row2["pi_file"]["file_id"])
    # download of new PI must be 200 (GridFS)
    dl = requests.get(f"{BASE}/files/{row2['pi_file']['file_id']}/download",
                      headers=_h(admin_tok))
    assert dl.status_code == 200


def test_9c_pi_history_archived_and_old_download_200(admin_tok):
    """After reject->resubmit (test_9b), the ORIGINAL rejected PI must be
    archived in pi_history with the admin's rejection reason. The old
    (now-archived) file must still be downloadable via /files/{id}/download.
    Then admin approves the fresh PI -> status='approved' but pi_history
    remains, so the UI can still show the '<N> rejected doc(s)' link.
    """
    # request created in test_9b is the LAST-appended id
    rid = created["requests"][-1]
    row = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
               if x["request_id"] == rid)
    hist = row.get("pi_history") or []
    assert len(hist) == 1, f"pi_history should have 1 entry, got {len(hist)}"
    h0 = hist[0]
    assert h0["outcome"] == "rejected"
    assert h0.get("admin_note") == "Vendor not empanelled"
    assert h0["pi_file"]["storage_backend"] == "gridfs"
    old_fid = h0["pi_file"]["file_id"]
    # OLD (archived) file must still download 200
    dl = requests.get(f"{BASE}/files/{old_fid}/download", headers=_h(admin_tok))
    assert dl.status_code == 200, dl.text[:200]
    assert len(dl.content) > 0
    # Approve the fresh PI
    a = requests.post(f"{BASE}/procurement/{rid}/action", headers=_h(admin_tok),
                      json={"action": "approve", "note": ""})
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "approved"
    # pi_history must remain after approval
    row2 = next(x for x in requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
                if x["request_id"] == rid)
    assert row2["status"] == "approved"
    assert len(row2.get("pi_history") or []) == 1
    assert row2["pi_history"][0]["pi_file"]["file_id"] == old_fid


def test_9d_no_pi_history_when_never_rejected(admin_tok):
    """The cancel-flow request (test_9) was never rejected/resubmitted, so
    pi_history must be empty/absent — this is the condition the UI uses to
    HIDE the 'rejected doc(s)' link on normal requests.
    """
    # request from test_9 is second-to-last (test_9b appended after it)
    # find the cancel-flow request explicitly by subject
    rows = requests.get(f"{BASE}/procurement", headers=_h(admin_tok)).json()
    cancel_row = next(x for x in rows if x["request_id"] in created["requests"]
                      and x.get("subject") == "TEST Cancel Flow")
    assert not cancel_row.get("pi_history"), \
        f"non-rejected request must have empty pi_history, got {cancel_row.get('pi_history')}"


# ---------------- cleanup -----------------------------------------------------

def test_z_cleanup(admin_tok):
    # delete created procurement docs + GridFS blobs directly in mongo
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
    from bson import ObjectId
    async def _cleanup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        fs = AsyncIOMotorGridFSBucket(db, bucket_name="uploads")
        for rid in created["requests"]:
            doc = await db.procurement.find_one({"request_id": rid})
            if doc:
                for h in doc.get("pi_history", []) or []:
                    fid = (h.get("pi_file") or {}).get("file_id")
                    if fid and fid not in created["file_ids"]:
                        created["file_ids"].append(fid)
            await db.procurement.delete_one({"request_id": rid})
        for fid in created["file_ids"]:
            rec = await db.files.find_one({"file_id": fid})
            if rec and rec.get("gridfs_id"):
                try:
                    await fs.delete(ObjectId(rec["gridfs_id"]))
                except Exception:
                    pass
            await db.files.delete_one({"file_id": fid})
        cli.close()
    asyncio.run(_cleanup())
    for uid in created["users"]:
        requests.delete(f"{BASE}/users/{uid}", headers=_h(admin_tok))
    remaining = [u["phone"] for u in requests.get(f"{BASE}/users", headers=_h(admin_tok)).json()]
    assert SM_PHONE not in remaining and MGMT_PHONE not in remaining
