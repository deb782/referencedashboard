"""Playwright E2E for Management role feature."""
import asyncio, os, json, time

URL = os.environ.get("PUBLIC_URL", "https://read-start-2.preview.emergentagent.com")

async def run(page):
    page.on("console", lambda m: print("CONSOLE:", m.type, m.text[:200]) if m.type in ("error","warning") else None)
    await page.set_viewport_size({"width":1400,"height":900})

    # ---------- Login as Admin ----------
    await page.goto(f"{URL}/login", wait_until="networkidle")
    await page.fill('[data-testid="login-phone"], input[name="phone"], input', "9513242807")
    # try common inputs
    inputs = await page.query_selector_all('input')
    if len(inputs) >= 2:
        await inputs[0].fill("9513242807")
        await inputs[1].fill("Repro@123")
    await page.click('button[type="submit"], [data-testid="login-submit"]')
    try:
        await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=15000)
        print("PASS: admin login")
    except Exception as e:
        print("FAIL admin login:", e)
        return

    # ---------- Cleanup any prior TEST users ----------
    token = await page.evaluate("() => localStorage.getItem('token')")
    import requests
    H = {"Authorization": f"Bearer {token}"}
    users = requests.get(f"{URL}/api/users", headers=H).json()
    for u in users:
        if u.get("phone") in ("9000000003","9000000004"):
            requests.delete(f"{URL}/api/users/{u['user_id']}", headers=H)
            print(f"cleanup pre: deleted {u['name']}")

    # Also cleanup TEST procurement
    procs = requests.get(f"{URL}/api/procurement", headers=H).json()
    for p in procs:
        if "TEST_" in p.get("subject",""):
            # No delete endpoint for procurement — mark for note
            print(f"note: leftover procurement {p['request_id']} subject={p['subject']}")

    # ---------- Go to Users page ----------
    await page.goto(f"{URL}/users", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="users-page"]')

    # Create Management user (perms: procurement + sales) for CVF
    await page.click('[data-testid="new-user-btn"]')
    await page.wait_for_selector('[data-testid="u-name"]')
    await page.fill('[data-testid="u-name"]', "TEST_MgmtCVF")
    await page.fill('[data-testid="u-phone"]', "9000000003")
    await page.select_option('[data-testid="u-role"]', "management")
    await page.wait_for_selector('[data-testid="u-proj"]')
    # Assert project select visible
    assert await page.is_visible('[data-testid="u-proj"]'), "u-proj select must appear for management role"
    await page.select_option('[data-testid="u-proj"]', "proj_01d7e89ba838")
    # Assert perm checklist visible
    for sec in ["projects","users","units","sales","inventory","procurement"]:
        assert await page.is_visible(f'[data-testid="perm-{sec}"]'), f"perm-{sec} missing"
    # click procurement + sales
    await page.click('[data-testid="perm-procurement"]')
    await page.click('[data-testid="perm-sales"]')
    await page.click('[data-testid="u-save"]')
    await page.wait_for_timeout(1500)
    print("PASS: created management user with perms procurement+sales")

    # Create Site Manager for CVF
    await page.click('[data-testid="new-user-btn"]')
    await page.wait_for_selector('[data-testid="u-name"]')
    await page.fill('[data-testid="u-name"]', "TEST_SiteCVF")
    await page.fill('[data-testid="u-phone"]', "9000000004")
    await page.select_option('[data-testid="u-role"]', "site_manager")
    await page.select_option('[data-testid="u-proj"]', "proj_01d7e89ba838")
    await page.click('[data-testid="u-save"]')
    await page.wait_for_timeout(1500)
    print("PASS: created site manager")

    # ---------- Test Access modal ----------
    users = requests.get(f"{URL}/api/users", headers=H).json()
    mgmt_user = next(u for u in users if u["phone"] == "9000000003")
    sm_user = next(u for u in users if u["phone"] == "9000000004")
    mgmt_id = mgmt_user["user_id"]
    sm_id = sm_user["user_id"]

    await page.wait_for_selector(f'[data-testid="access-{mgmt_id}"]')
    await page.click(f'[data-testid="access-{mgmt_id}"]')
    await page.wait_for_selector('[data-testid="access-save"]')
    for sec in ["projects","users","units","sales","inventory","procurement"]:
        assert await page.is_visible(f'[data-testid="access-perm-{sec}"]'), f"access-perm-{sec} missing"
    # sales is checked already; toggle inventory ON as extra
    await page.click('[data-testid="access-perm-inventory"]')
    await page.click('[data-testid="access-save"]')
    await page.wait_for_timeout(1500)
    # verify via api
    users = requests.get(f"{URL}/api/users", headers=H).json()
    mgmt_user = next(u for u in users if u["phone"] == "9000000003")
    print("mgmt perms after access edit:", mgmt_user.get("permissions"))
    assert "inventory" in mgmt_user["permissions"], "inventory not added via access modal"
    # revert: toggle back off so end-state = procurement+sales
    await page.click(f'[data-testid="access-{mgmt_id}"]')
    await page.wait_for_selector('[data-testid="access-save"]')
    await page.click('[data-testid="access-perm-inventory"]')
    await page.click('[data-testid="access-save"]')
    await page.wait_for_timeout(1500)
    print("PASS: access modal edit works")

    # ---------- Site Manager raises procurement ----------
    sm_token = requests.post(f"{URL}/api/auth/login", json={"phone":"9000000004","password":"9000000004"}).json()
    if "access_token" not in sm_token:
        print("Site manager still needs first reset. Reset via change-password after login.")
    # Reset via API by logging in then changing password
    sm_hdr = {"Authorization": f"Bearer {sm_token['access_token']}"}
    r = requests.post(f"{URL}/api/auth/change-password", headers=sm_hdr,
                      json={"current_password":"9000000004","new_password":"Pass@1234"})
    print("SM change-password:", r.status_code)
    sm_login = requests.post(f"{URL}/api/auth/login", json={"phone":"9000000004","password":"Pass@1234"}).json()
    sm_hdr = {"Authorization": f"Bearer {sm_login['access_token']}"}
    # raise procurement (multipart form)
    import io as _io
    fd = {
        "project_id": (None, "proj_01d7e89ba838"),
        "subject": (None, "TEST_MgmtFlow"),
        "items": (None, json.dumps([{"name":"Cement","quantity":10,"unit":"bags","est_cost":500}])),
        "priority": (None, "high"),
        "notes": (None, "mgmt flow test"),
    }
    r = requests.post(f"{URL}/api/procurement", headers=sm_hdr, files=fd)
    print("proc create status:", r.status_code, r.text[:200])
    proc = r.json()
    assert proc["status"] == "pending_management", f"expected pending_management, got {proc['status']}"
    print(f"PASS: procurement created with status={proc['status']}")
    proc_id = proc["request_id"]

    # ---------- Login as Management ----------
    await page.evaluate("() => localStorage.clear()")
    await page.goto(f"{URL}/login", wait_until="networkidle")
    inputs = await page.query_selector_all('input')
    await inputs[0].fill("9000000003")
    await inputs[1].fill("9000000003")
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(2500)
    # expect force reset page
    url_now = page.url
    print("post-mgmt-login url:", url_now)
    # Look for reset password inputs
    reset_inputs = await page.query_selector_all('input[type="password"]')
    print("password inputs count:", len(reset_inputs))
    if len(reset_inputs) >= 2:
        # Reset password
        for inp in reset_inputs:
            await inp.fill("Pass@1234")
        # find submit
        submit_btn = await page.query_selector('button[type="submit"], button:has-text("Reset"), button:has-text("Update")')
        if submit_btn:
            await submit_btn.click()
        await page.wait_for_timeout(2500)
        print("PASS: password reset submitted")
    # now expect dashboard
    try:
        await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=10000)
        print("PASS: mgmt lands on dashboard-page")
    except Exception as e:
        print("FAIL mgmt dashboard:", e, "url=", page.url)

    # verify badge + approvals kpi
    assert await page.is_visible('[data-testid="mgmt-project-badge"]'), "mgmt-project-badge missing"
    badge_text = await page.text_content('[data-testid="mgmt-project-badge"]')
    print("badge:", badge_text)
    assert "Central Vista" in badge_text, f"badge should contain CVF, got {badge_text}"
    assert await page.is_visible('[data-testid="mgmt-approvals-kpi"]'), "mgmt-approvals-kpi missing"
    kpi_text = await page.text_content('[data-testid="mgmt-approvals-kpi"]')
    print("kpi:", kpi_text.replace("\n"," ")[:200])
    # project pivot
    assert await page.is_visible('[data-testid="dash-project-proj_01d7e89ba838"]'), "dash-project pivot missing"
    print("PASS: mgmt dashboard widgets ok")

    # ---------- Sidebar filtering ----------
    for allowed in ["dashboard","sales","procurement"]:
        assert await page.is_visible(f'[data-testid="nav-{allowed}"]'), f"nav-{allowed} missing"
    for denied in ["projects","users","units","inventory"]:
        vis = await page.query_selector(f'[data-testid="nav-{denied}"]')
        assert vis is None, f"nav-{denied} should NOT be visible for mgmt (perms=procurement+sales)"
    print("PASS: sidebar filters to Dashboard+Sales+Procurement only")

    # ---------- Direct URL redirect check ----------
    await page.goto(f"{URL}/users", wait_until="networkidle")
    await page.wait_for_timeout(1200)
    print("direct /users url now:", page.url)
    # should be /dashboard
    assert page.url.endswith("/dashboard"), f"expected redirect to /dashboard, got {page.url}"
    print("PASS: /users redirects to /dashboard for mgmt without perm")

    await page.goto(f"{URL}/inventory", wait_until="networkidle")
    await page.wait_for_timeout(1200)
    assert page.url.endswith("/dashboard"), f"expected redirect from /inventory, got {page.url}"
    print("PASS: /inventory redirects to /dashboard")

    # ---------- Sales view-only ----------
    await page.goto(f"{URL}/sales", wait_until="networkidle")
    await page.wait_for_timeout(2000)
    # No record-payment button visible
    rp = await page.query_selector('[data-testid^="receipt-btn-"]')
    assert rp is None, "record-payment button should be hidden for mgmt"
    verify_btn = await page.query_selector('[data-testid^="vq-yes-"], [data-testid^="vq-no-"]')
    assert verify_btn is None, "verify buttons should be hidden for mgmt"
    print("PASS: Sales page view-only for mgmt")

    # ---------- Procurement Review button check ----------
    await page.goto(f"{URL}/procurement", wait_until="networkidle")
    await page.wait_for_timeout(2000)
    review_selector = f'[data-testid="mgmt-review-{proc_id}"]'
    fallback_selector = f'[data-testid="review-{proc_id}"]'
    has_mgmt_review = await page.query_selector(review_selector) is not None
    has_review = await page.query_selector(fallback_selector) is not None
    print(f"mgmt-review-{proc_id} visible:", has_mgmt_review, " review-{id} visible:", has_review)
    proc_row_exists = await page.query_selector(f'[data-testid="proc-row-{proc_id}"]') is not None
    print(f"proc-row-{proc_id} present:", proc_row_exists)
    if not (has_mgmt_review or has_review):
        print("BUG: Management user cannot see any Review button for pending_management procurement")

    # ---------- Regression: procurement with no mgmt user goes to pending_admin ----------
    # Vacation Village has no management user assigned
    # Create SM for VV to raise a request there
    # Actually we can create the procurement as admin (admin role allowed): admin token
    admin_login = requests.post(f"{URL}/api/auth/login", json={"phone":"9513242807","password":"Repro@123"}).json()
    ah = {"Authorization": f"Bearer {admin_login['access_token']}"}
    fd2 = {
        "project_id": (None, "proj_53fb360c1f0a"),
        "subject": (None, "TEST_NoMgmtFlow"),
        "items": (None, json.dumps([{"name":"Sand","quantity":5,"unit":"tons","est_cost":300}])),
        "priority": (None, "low"),
        "notes": (None,""),
    }
    r2 = requests.post(f"{URL}/api/procurement", headers=ah, files=fd2)
    p2 = r2.json()
    print("VV proc status:", p2.get("status"))
    assert p2["status"] == "pending_admin", f"VV (no mgmt user) should be pending_admin, got {p2.get('status')}"
    print("PASS: regression - project without mgmt user goes directly to pending_admin")
    proc2_id = p2["request_id"]

    # ---------- Branding ----------
    branding = await page.text_content('aside')
    assert "Management Dashboard" in branding, "sidebar should show 'Management Dashboard'"
    assert "Stakeholder Console" in branding, "sidebar should show 'Stakeholder Console'"
    print("PASS: branding correct")

    # ---------- Cleanup ----------
    # Delete test procurement docs via DB not possible via API; note and skip
    # Delete users
    for uid in [mgmt_id, sm_id]:
        r = requests.delete(f"{URL}/api/users/{uid}", headers=ah)
        print("delete user", uid, r.status_code)
    print("Cleanup done. Note: 2 test procurement docs remain (no delete endpoint):", proc_id, proc2_id)


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context()
        page = await ctx.new_page()
        try:
            await run(page)
        except Exception as e:
            import traceback; traceback.print_exc()
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
