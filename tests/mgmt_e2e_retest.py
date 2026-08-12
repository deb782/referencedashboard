"""Retest for Management role fixes (iter 18): mgmt Review button + /reset-password branding + regression."""
import asyncio, os, json, sys, traceback
import requests
from pymongo import MongoClient

URL = "https://read-start-2.preview.emergentagent.com"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "agrocorp_lite"
CVF = "proj_01d7e89ba838"
VV  = "proj_53fb360c1f0a"

RESULTS = []
def rec(name, ok, note=""):
    RESULTS.append((name, ok, note))
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" -- {note}" if note else ""))

def admin_token():
    r = requests.post(f"{URL}/api/auth/login", json={"phone":"9513242807","password":"Repro@123"})
    return r.json()["access_token"]

def cleanup(atok):
    H = {"Authorization": f"Bearer {atok}"}
    users = requests.get(f"{URL}/api/users", headers=H).json()
    for u in users:
        if u.get("phone") in ("9000000003","9000000004","9000000005"):
            requests.delete(f"{URL}/api/users/{u['user_id']}", headers=H)
    # Mongo cleanup
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    procs = list(db.procurement.find({"subject": {"$regex":"^TEST_"}}))
    ids = [p["request_id"] for p in procs]
    db.procurement.delete_many({"subject": {"$regex":"^TEST_"}})
    if ids:
        db.notifications.delete_many({"data.request_id": {"$in": ids}})
    cli.close()
    print("Cleanup: users+", len(ids), "procs+notifs removed")

async def run(page):
    atok = admin_token()
    cleanup(atok)  # pre-clean
    H = {"Authorization": f"Bearer {atok}"}

    # 1. Create users via API for speed (Team page already tested in iter17)
    for name, phone, role, perms in [
        ("TEST_MgmtCVF","9000000003","management",["procurement","sales"]),
        ("TEST_SiteCVF","9000000004","site_manager",[]),
    ]:
        payload = {"name":name,"phone":phone,"role":role,"project_id":CVF,"permissions":perms}
        r = requests.post(f"{URL}/api/users", headers=H, json=payload)
        assert r.status_code in (200,201), f"user create {name}: {r.status_code} {r.text[:200]}"
    users = requests.get(f"{URL}/api/users", headers=H).json()
    mgmt_id = next(u["user_id"] for u in users if u["phone"]=="9000000003")
    sm_id   = next(u["user_id"] for u in users if u["phone"]=="9000000004")
    rec("create test users", True)

    # 2. Site Manager reset password + raise procurement
    r = requests.post(f"{URL}/api/auth/login", json={"phone":"9000000004","password":"9000000004"}).json()
    smh = {"Authorization": f"Bearer {r['access_token']}"}
    requests.post(f"{URL}/api/auth/change-password", headers=smh,
                  json={"current_password":"9000000004","new_password":"Pass@1234"})
    smh = {"Authorization": f"Bearer {requests.post(f'{URL}/api/auth/login', json={'phone':'9000000004','password':'Pass@1234'}).json()['access_token']}"}
    def raise_req(subject):
        fd = {
            "project_id": (None, CVF), "subject": (None, subject),
            "items": (None, json.dumps([{"name":"Cement","quantity":10,"unit":"bags","est_cost":500}])),
            "priority": (None, "high"), "notes": (None, "test"),
        }
        r = requests.post(f"{URL}/api/procurement", headers=smh, files=fd)
        return r.json()
    p_approve = raise_req("TEST_MgmtApprove")
    p_reject  = raise_req("TEST_MgmtReject")
    p_clarify = raise_req("TEST_MgmtClarify")
    for p in [p_approve, p_reject, p_clarify]:
        assert p.get("status") == "pending_management", f"expected pending_management got {p}"
    rec("SM raised 3 requests, all pending_management", True)

    # 3. Verify /reset-password branding via UI
    # Reset mgmt password to a fresh mgmt user so we hit reset-password page. First, log in with default password.
    await page.set_viewport_size({"width":1400,"height":900})
    await page.goto(f"{URL}/login", wait_until="networkidle")
    ins = await page.query_selector_all('input')
    await ins[0].fill("9000000003"); await ins[1].fill("9000000003")
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(3000)
    # Should be at /reset-password
    on_reset = "/reset-password" in page.url or await page.query_selector('input[type="password"]') is not None
    print("reset page url:", page.url)
    # Check branding
    body = await page.text_content('body')
    has_mgmt = "Management Dashboard" in body
    has_stake = "Stakeholder Console" in body
    has_lite = "Agrocorp Lite" in body
    has_logo = await page.query_selector('img[src*="agrocorp-logo"]') is not None
    rec("/reset-password: 'Management Dashboard' branding present", has_mgmt, body[:120])
    rec("/reset-password: 'Stakeholder Console' branding present", has_stake)
    rec("/reset-password: NO 'Agrocorp Lite' text", not has_lite)
    rec("/reset-password: agrocorp-logo.webp img present", has_logo)

    # Reset password (current=phone, new/confirm=Pass@1234)
    await page.fill('[data-testid="rp-current"]', "9000000003")
    await page.fill('[data-testid="rp-new"]', "Pass@1234")
    await page.fill('[data-testid="rp-confirm"]', "Pass@1234")
    await page.click('[data-testid="rp-submit"]')
    await page.wait_for_timeout(3500)

    # 4. Regression: mgmt dashboard
    try:
        await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=10000)
        rec("mgmt dashboard-page loads", True)
    except Exception as e:
        rec("mgmt dashboard-page loads", False, str(e))
    badge_ok = await page.is_visible('[data-testid="mgmt-project-badge"]')
    kpi_ok   = await page.is_visible('[data-testid="mgmt-approvals-kpi"]')
    badge_txt = await page.text_content('[data-testid="mgmt-project-badge"]') if badge_ok else ""
    rec("mgmt-project-badge visible + CVF", badge_ok and "Central Vista" in badge_txt, badge_txt)
    rec("mgmt-approvals-kpi visible", kpi_ok)
    # sidebar filter
    for allowed in ["dashboard","sales","procurement"]:
        v = await page.query_selector(f'[data-testid="nav-{allowed}"]')
        rec(f"sidebar has nav-{allowed}", v is not None)
    for denied in ["projects","users","units","inventory"]:
        v = await page.query_selector(f'[data-testid="nav-{denied}"]')
        rec(f"sidebar hides nav-{denied}", v is None)
    # redirect
    await page.goto(f"{URL}/users", wait_until="networkidle")
    await page.wait_for_timeout(1200)
    rec("/users redirects to /dashboard for mgmt", page.url.endswith("/dashboard"), page.url)
    await page.goto(f"{URL}/inventory", wait_until="networkidle")
    await page.wait_for_timeout(1200)
    rec("/inventory redirects to /dashboard for mgmt", page.url.endswith("/dashboard"), page.url)

    # 5. Procurement page: mgmt-review buttons
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    for p in [p_approve, p_reject, p_clarify]:
        pid = p["request_id"]
        btn = await page.query_selector(f'[data-testid="mgmt-review-{pid}"]')
        rec(f"mgmt-review-{pid[:12]} button present", btn is not None)

    # 5a. Reject requires note
    rid = p_reject["request_id"]
    await page.click(f'[data-testid="mgmt-review-{rid}"]')
    await page.wait_for_selector('[data-testid="act-submit"]')
    await page.click('[data-testid="act-reject"]')
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(1200)
    # dialog should still be open (toast error), status still pending_management
    still_open = await page.query_selector('[data-testid="act-submit"]') is not None
    rec("Reject without note blocked (dialog remains)", still_open)
    await page.fill('[data-testid="act-note"]', "Not required now")
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(2500)
    # Check status via API
    procs = requests.get(f"{URL}/api/procurement", headers=H).json()
    pr = next(x for x in procs if x["request_id"]==rid)
    rec("Reject with note -> status=rejected", pr["status"]=="rejected", pr["status"])

    # 5b. Clarify requires note
    cid = p_clarify["request_id"]
    # request list may need reload
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2000)
    await page.click(f'[data-testid="mgmt-review-{cid}"]')
    await page.wait_for_selector('[data-testid="act-submit"]')
    await page.click('[data-testid="act-clarify"]')
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(1000)
    still_open2 = await page.query_selector('[data-testid="act-submit"]') is not None
    rec("Clarify without note blocked", still_open2)
    await page.fill('[data-testid="act-note"]', "Please attach quotes")
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(2500)
    procs = requests.get(f"{URL}/api/procurement", headers=H).json()
    pc = next(x for x in procs if x["request_id"]==cid)
    rec("Clarify with note -> status=management_clarification", pc["status"]=="management_clarification", pc["status"])

    # 5c. Approve -> pending_admin
    aid = p_approve["request_id"]
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2000)
    await page.click(f'[data-testid="mgmt-review-{aid}"]')
    await page.wait_for_selector('[data-testid="act-submit"]')
    await page.click('[data-testid="act-approve"]')
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(2500)
    procs = requests.get(f"{URL}/api/procurement", headers=H).json()
    pa = next(x for x in procs if x["request_id"]==aid)
    rec("Approve -> status=pending_admin", pa["status"]=="pending_admin", pa["status"])

    # 6. Admin login and approve
    await page.evaluate("() => localStorage.clear()")
    await page.goto(f"{URL}/login", wait_until="networkidle")
    ins = await page.query_selector_all('input')
    await ins[0].fill("9513242807"); await ins[1].fill("Repro@123")
    await page.click('button[type="submit"]')
    await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=10000)
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    admin_btn = await page.query_selector(f'[data-testid="review-{aid}"]')
    rec(f"admin sees review-{aid[:12]} button", admin_btn is not None)
    await page.click(f'[data-testid="review-{aid}"]')
    await page.wait_for_selector('[data-testid="act-submit"]')
    await page.click('[data-testid="act-approve"]')
    await page.click('[data-testid="act-submit"]')
    await page.wait_for_timeout(2500)
    procs = requests.get(f"{URL}/api/procurement", headers=H).json()
    pa = next(x for x in procs if x["request_id"]==aid)
    rec("Admin approve -> status=approved", pa["status"]=="approved", pa["status"])

    # 7. Accounts issues PO
    acc_tok = requests.post(f"{URL}/api/auth/login", json={"phone":"9000000002","password":"Pass@123"}).json()["access_token"]
    await page.evaluate("() => localStorage.clear()")
    await page.goto(f"{URL}/login", wait_until="networkidle")
    ins = await page.query_selector_all('input')
    await ins[0].fill("9000000002"); await ins[1].fill("Pass@123")
    await page.click('button[type="submit"]')
    await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=10000)
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    po_btn = await page.query_selector(f'[data-testid="po-{aid}"]')
    rec(f"accounts sees Issue PO button", po_btn is not None)
    if po_btn:
        await po_btn.click()
        await page.wait_for_selector('[data-testid="po-submit"]')
        # fill PO number
        await page.fill('[data-testid="po-number"]', "PO-TEST-001")
        await page.click('[data-testid="po-submit"]')
        await page.wait_for_timeout(2500)
        procs = requests.get(f"{URL}/api/procurement", headers=H).json()
        pa = next(x for x in procs if x["request_id"]==aid)
        rec("Accounts PO issued -> status in [po_issued,paid]", pa["status"] in ["po_issued","paid"], pa["status"])

    # cleanup
    cleanup(atok)

    # Summary
    passed = sum(1 for _,ok,_ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n===== SUMMARY: {passed}/{total} passed =====")
    for n,ok,note in RESULTS:
        if not ok:
            print(" FAIL:", n, note)

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context()
        page = await ctx.new_page()
        try:
            await run(page)
        except Exception as e:
            traceback.print_exc()
        finally:
            await b.close()

if __name__ == "__main__":
    asyncio.run(main())
