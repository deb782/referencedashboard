import os, asyncio, httpx
from motor.motor_asyncio import AsyncIOMotorClient

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')
CVF = "proj_01d7e89ba838"


async def login(c, ph, pw):
    r = await c.post(f"{API}/api/auth/login", json={"phone": ph, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main():
    db = AsyncIOMotorClient(M)[D]
    async with httpx.AsyncClient(timeout=60) as c:
        ps = await login(c, "9000000001", "Pass@123")
        ad = await login(c, "9513242807", "Repro@123")

        proj = await db.projects.find_one({"project_id": CVF}, {"_id": 0})
        cks = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        vcfg = proj["vault_config"]
        v7 = next(v for v in vcfg["variants"] if v["variant_id"] == "7000")
        # pick a CVF available plot WITH data (grand total > 0)
        units = await db.units.find({"project_id": CVF, "status": "available"}, {"_id": 0}).to_list(200)
        unit = next(u for u in units if sum(float(u["data"].get(k) or 0) for k in cks) > 0)
        uid = unit["unit_id"]
        gt = round(sum(float(unit["data"].get(k) or 0) for k in cks), 2)
        print("plot", unit["plot_number"], "land GT", gt, "vault total", v7["total"])

        # land schedule = 2 rows summing to GT ; vault schedule from template (10x10%)
        land = [{"due_date": "2026-07-01", "amount": round(gt / 2, 2), "notes": "Booking"},
                {"due_date": "2026-09-01", "amount": round(gt - round(gt / 2, 2), 2), "notes": "Balance"}]
        vt = v7["total"]; step = round(vt / 10, 2); acc = 0; vs = []
        for i in range(10):
            amt = step if i < 9 else round(vt - acc, 2)
            acc = round(acc + amt, 2)
            vs.append({"due_date": "2026-08-01", "amount": amt, "notes": f"Vault {i+1}"})

        r = await c.post(f"{API}/api/units/{uid}/sell", headers=ps, json={
            "buyer_name": "Vault Buyer", "sale_date": "2026-06-01", "final_price": gt,
            "booking_amount": land[0]["amount"], "schedule": land,
            "vault": {"variant_id": "7000", "label": v7["label"], "construction": v7["construction"],
                      "gst": v7["gst"], "total": v7["total"]},
            "vault_schedule": vs})
        print("sell w/ vault:", r.status_code, r.text[:120])
        assert r.status_code == 200, r.text

        pays = await db.payments.find({"unit_id": uid}, {"_id": 0}).to_list(50)
        land_p = [p for p in pays if p.get("stream", "land") == "land"]
        vault_p = [p for p in pays if p.get("stream") == "vault"]
        print("land instalments:", len(land_p), "vault instalments:", len(vault_p))
        assert len(land_p) == 2 and len(vault_p) == 10
        assert abs(sum(p["amount"] for p in vault_p) - vt) < 1

        # unit.vault stored
        u2 = await db.units.find_one({"unit_id": uid}, {"_id": 0})
        assert u2.get("vault", {}).get("enabled") and abs(u2["vault"]["total"] - vt) < 1

        # reject a vault schedule that doesn't sum to vault total (edit)
        r = await c.put(f"{API}/api/units/{uid}/schedule", headers=ps, json={
            "stream": "vault",
            "installments": [{"payment_id": vault_p[0]["payment_id"], "due_date": "2026-08-01",
                              "amount": 123, "notes": "x"}]})
        print("bad vault edit:", r.status_code)
        assert r.status_code == 400

        # break vault schedule directly -> mismatched-plots should flag the VAULT stream
        await db.payments.update_one({"payment_id": vault_p[0]["payment_id"]},
                                     {"$set": {"amount": round(vault_p[0]["amount"] - 5000, 2)}})
        r = await c.get(f"{API}/api/mismatched-plots", headers=ps, params={"project_id": CVF})
        mm = [i for i in r.json()["items"] if i["unit_id"] == uid]
        streams = {i["stream"] for i in mm}
        print("mismatched streams:", streams, "diffs:", [(i["stream"], i["difference"]) for i in mm])
        assert "vault" in streams and "land" not in streams

        # dashboard stream breakdown
        r = await c.get(f"{API}/api/dashboard", headers=ad)
        proj_row = next(p for p in r.json()["by_project"] if p["project_id"] == CVF)
        print("has_vault:", proj_row["has_vault"], "streams:", proj_row["streams"])
        assert proj_row["has_vault"] and abs(proj_row["streams"]["vault"]["billed"] - vt) < 1
        assert proj_row["streams"]["vault"]["attach_count"] == 1
        con = r.json()["consolidated"]
        print("consolidated vault_booked:", con.get("vault_booked"), "attach:", con.get("vault_attach"))
        assert abs(con.get("vault_booked", 0) - vt) < 1

        # cleanup
        await db.payments.delete_many({"unit_id": uid})
        await db.schedule_logs.delete_many({"unit_id": uid})
        await db.schedule_revisions.delete_many({"unit_id": uid})
        await db.units.update_one({"unit_id": uid}, {"$set": {"status": "available"},
            "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "", "final_price": "",
                       "booking_amount": "", "sold_by": "", "sold_at": "", "vault": ""}})
        print("CLEANED. CVF sold:", await db.units.count_documents({"project_id": CVF, "status": "sold"}),
              "VV units:", await db.units.count_documents({"project_id": "proj_53fb360c1f0a"}))
        print("ALL PASS")


asyncio.run(main())
