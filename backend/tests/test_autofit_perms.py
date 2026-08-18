import os, httpx, asyncio

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()

async def login(c, phone, pwd):
    r = await c.post(f"{API}/api/auth/login", json={"phone": phone, "password": pwd})
    return r.json()["access_token"]

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # accounts
        tok = await login(c, "9000000002", "Pass@123")
        H = {"Authorization": f"Bearer {tok}"}
        r1 = await c.get(f"{API}/api/mismatched-plots", headers=H)
        print("accounts GET mismatched-plots:", r1.status_code)
        assert r1.status_code == 403, r1.text
        r2 = await c.post(f"{API}/api/units/fake/auto-fit-schedule", headers=H, json={"payment_id": "x"})
        print("accounts POST auto-fit-schedule:", r2.status_code)
        assert r2.status_code == 403, r2.text
        # post_sales positive
        tok2 = await login(c, "9000000001", "Pass@123")
        H2 = {"Authorization": f"Bearer {tok2}"}
        r3 = await c.get(f"{API}/api/mismatched-plots", headers=H2)
        print("post_sales GET mismatched-plots:", r3.status_code)
        assert r3.status_code == 200
        # admin positive
        tok3 = await login(c, "9513242807", "Repro@123")
        H3 = {"Authorization": f"Bearer {tok3}"}
        r4 = await c.get(f"{API}/api/mismatched-plots", headers=H3)
        print("admin GET mismatched-plots:", r4.status_code)
        assert r4.status_code == 200
        print("PERMS PASS")

asyncio.run(main())
