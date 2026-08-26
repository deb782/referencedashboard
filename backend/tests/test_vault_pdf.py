import os, asyncio, httpx, io
from motor.motor_asyncio import AsyncIOMotorClient
from pypdf import PdfReader

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')
CVF = "proj_01d7e89ba838"


async def login(c, ph, pw):
    r = await c.post(f"{API}/api/auth/login", json={"phone": ph, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main():
    db = AsyncIOMotorClient(M)[D]
    async with httpx.AsyncClient(timeout=90) as c:
        ps = await login(c, "9000000001", "Pass@123")
        proj = await db.projects.find_one({"project_id": CVF}, {"_id": 0})
        cks = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        v7 = next(v for v in proj["vault_config"]["variants"] if v["variant_id"] == "7000")
        units = await db.units.find({"project_id": CVF, "status": "available"}, {"_id": 0}).to_list(200)
        unit = next(u for u in units if sum(float(u["data"].get(k) or 0) for k in cks) > 0)
        uid = unit["unit_id"]
        gt = round(sum(float(unit["data"].get(k) or 0) for k in cks), 2)
        vt = v7["total"]; step = round(vt / 10, 2); acc = 0; vs = []
        for i in range(10):
            amt = step if i < 9 else round(vt - acc, 2); acc = round(acc + amt, 2)
            vs.append({"due_date": "2026-08-01", "amount": amt, "notes": f"Vault {i+1}"})
        r = await c.post(f"{API}/api/units/{uid}/sell", headers=ps, json={
            "buyer_name": "PDF Vault", "sale_date": "2026-06-01", "final_price": gt,
            "booking_amount": round(gt/2,2),
            "schedule": [{"due_date":"2026-07-01","amount":round(gt/2,2),"notes":"Booking"},
                         {"due_date":"2026-09-01","amount":round(gt-round(gt/2,2),2),"notes":"Balance"}],
            "vault": {"variant_id":"7000","label":v7["label"],"construction":v7["construction"],"gst":v7["gst"],"total":vt},
            "vault_schedule": vs})
        assert r.status_code == 200, r.text
        rp = await c.get(f"{API}/api/units/{uid}/payment-report", headers=ps)
        assert rp.status_code == 200 and rp.content[:4] == b"%PDF", (rp.status_code, rp.content[:20])
        text = "".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(rp.content)).pages)
        has_vault_hdr = "The Vault" in text
        has_construction = "Construction" in text
        has_land = "Land" in text
        print("PDF has 'The Vault':", has_vault_hdr, "| 'Construction':", has_construction, "| 'Land':", has_land)
        print("Vault total in text:", "91,45,000" in text or "9145000" in text or "9,145,000" in text)
        assert has_vault_hdr and has_construction
        # cleanup
        await db.payments.delete_many({"unit_id": uid}); await db.schedule_logs.delete_many({"unit_id": uid})
        await db.units.update_one({"unit_id": uid}, {"$set":{"status":"available"},
            "$unset":{"buyer_name":"","buyer_contact":"","sale_date":"","final_price":"","booking_amount":"","sold_by":"","sold_at":"","vault":""}})
        print("CLEANED CVF sold:", await db.units.count_documents({"project_id":CVF,"status":"sold"}))
        print("PASS")

asyncio.run(main())
