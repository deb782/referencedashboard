import os, asyncio, httpx
from motor.motor_asyncio import AsyncIOMotorClient

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()
MONGO = os.popen("grep MONGO_URL /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')
DBN = os.popen("grep DB_NAME /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')


async def login(c, phone, pwd):
    r = await c.post(f"{API}/api/auth/login", json={"phone": phone, "password": pwd})
    return r.json()["access_token"]


async def main():
    db = AsyncIOMotorClient(MONGO)[DBN]
    async with httpx.AsyncClient(timeout=60) as c:
        ps = {"Authorization": f"Bearer {await login(c, '9000000001', 'Pass@123')}"}
        ac = {"Authorization": f"Bearer {await login(c, '9000000002', 'Pass@123')}"}

        proj = await db.projects.find_one({"name": {"$regex": "Central Vista", "$options": "i"}})
        cks = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        clabel = {x["key"]: x.get("label", x["key"]) for x in proj["columns"] if x["tag"] == "charge"}
        unit = await db.units.find_one({"project_id": proj["project_id"], "status": "available",
                                        "$expr": {"$gt": [{"$size": {"$objectToArray": "$data"}}, 0]}})
        uid = unit["unit_id"]
        gt = round(sum(float(unit["data"].get(k) or 0) for k in cks), 2)
        a, b = round(gt * 0.5, 2), round(gt * 0.5, 2)
        b = round(gt - a, 2)
        sched = [{"due_date": "2026-07-01", "amount": a, "notes": "A"},
                 {"due_date": "2026-08-01", "amount": b, "notes": "B"}]
        r = await c.post(f"{API}/api/units/{uid}/sell", headers=ps, json={
            "buyer_name": "Bif Test", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gt, "booking_amount": a, "schedule": sched})
        assert r.status_code == 200, r.text
        pays = await db.payments.find({"unit_id": uid}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        pA, pB = pays

        async def add_verify(pid, amt, allocs=None):
            r = await c.post(f"{API}/api/payments/{pid}/receipt", headers=ps,
                             json={"amount": amt, "date": "2026-07-02", "mode": "neft",
                                   "head": "BSP Collection", "allocations": allocs or []})
            assert r.status_code == 200, r.text
            doc = await db.payments.find_one({"payment_id": pid}, {"_id": 0})
            rc = doc["receipts"][-1]["receipt_id"]
            r = await c.post(f"{API}/api/payments/{pid}/receipts/{rc}/verify", headers=ac,
                             json={"decision": "yes"})
            assert r.status_code == 200, r.text

        first_key = cks[0]
        # A: verified WITH allocation (bifurcated)
        await add_verify(pA["payment_id"], round(a * 0.5, 2),
                         allocs=[{"key": first_key, "label": clabel[first_key], "amount": round(a * 0.5, 2)}])
        # B: verified WITHOUT allocation (unbifurcated)
        await add_verify(pB["payment_id"], round(b * 0.3, 2))

        r = await c.get(f"{API}/api/bifurcation-progress", headers=ps,
                        params={"project_id": proj["project_id"]})
        d = r.json()
        item = next(i for i in d["items"] if i["project_id"] == proj["project_id"])
        exp_v = round(a * 0.5 + b * 0.3, 2)
        exp_b = round(a * 0.5, 2)
        print("verified", item["verified"], "bifurcated", item["bifurcated"],
              "pct", item["pct"], "pending", item["pending_receipts"])
        assert abs(item["verified"] - exp_v) < 1, (item["verified"], exp_v)
        assert abs(item["bifurcated"] - exp_b) < 1, (item["bifurcated"], exp_b)
        assert item["pending_receipts"] == 1
        assert abs(item["pct"] - round(exp_b / exp_v * 100, 1)) < 0.2

        # management can read, no auth -> handled by role dep
        r = await c.get(f"{API}/api/bifurcation-progress", headers=ac)
        assert r.status_code == 200

        # cleanup
        await db.payments.delete_many({"unit_id": uid})
        await db.schedule_logs.delete_many({"unit_id": uid})
        await db.schedule_revisions.delete_many({"unit_id": uid})
        await db.units.update_one({"unit_id": uid}, {"$set": {"status": "available"},
            "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "", "final_price": "",
                       "booking_amount": "", "sold_by": "", "sold_at": ""}})
        print("CLEANED sold:", await db.units.count_documents({"status": "sold"}),
              "payments:", await db.payments.count_documents({}))
        print("ALL PASS")


asyncio.run(main())
