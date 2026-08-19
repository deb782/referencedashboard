"""Seed a mismatched plot AND a plot with a verified receipt, for UI testing.
Prints plot numbers. Also has a cleanup mode with argv[1]=='cleanup'."""
import os, asyncio, sys, httpx
from motor.motor_asyncio import AsyncIOMotorClient

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()
MONGO = os.popen("grep MONGO_URL /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')
DBN = os.popen("grep DB_NAME /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')


async def login(c, phone, pwd):
    r = await c.post(f"{API}/api/auth/login", json={"phone": phone, "password": pwd})
    return r.json()["access_token"]


async def cleanup():
    db = AsyncIOMotorClient(MONGO)[DBN]
    sold = [u async for u in db.units.find({"status": "sold"}, {"unit_id": 1})]
    ids = [u["unit_id"] for u in sold]
    if ids:
        await db.payments.delete_many({"unit_id": {"$in": ids}})
        await db.schedule_logs.delete_many({"unit_id": {"$in": ids}})
        await db.schedule_revisions.delete_many({"unit_id": {"$in": ids}})
        await db.units.update_many({"unit_id": {"$in": ids}}, {
            "$set": {"status": "available"},
            "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                       "final_price": "", "booking_amount": "", "sold_by": "", "sold_at": ""}})
    print("cleanup sold:", await db.units.count_documents({"status": "sold"}),
          "pay:", await db.payments.count_documents({}),
          "rev:", await db.schedule_revisions.count_documents({}))


async def seed():
    db = AsyncIOMotorClient(MONGO)[DBN]
    async with httpx.AsyncClient(timeout=60) as c:
        ps = {"Authorization": f"Bearer {await login(c, '9000000001', 'Pass@123')}"}
        ac = {"Authorization": f"Bearer {await login(c, '9000000002', 'Pass@123')}"}

        proj = await db.projects.find_one({"name": {"$regex": "Central Vista", "$options": "i"}})
        cks = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        avail = [u async for u in db.units.find({"project_id": proj["project_id"], "status": "available",
                 "$expr": {"$gt": [{"$size": {"$objectToArray": "$data"}}, 0]}}).limit(5)]
        # ---- Plot A: mismatch (tamper amount) ----
        uA = avail[0]
        gtA = round(sum(float(uA["data"].get(k) or 0) for k in cks), 2)
        half = round(gtA / 2, 2)
        sched = [{"due_date": "2026-07-01", "amount": half, "notes": "Booking"},
                 {"due_date": "2026-09-01", "amount": round(gtA - half, 2), "notes": "Balance"}]
        r = await c.post(f"{API}/api/units/{uA['unit_id']}/sell", headers=ps, json={
            "buyer_name": "UI Mismatch", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gtA, "booking_amount": half, "schedule": sched})
        assert r.status_code == 200, r.text
        pays = await db.payments.find({"unit_id": uA["unit_id"]}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        await db.payments.update_one({"payment_id": pays[1]["payment_id"]},
                                     {"$set": {"amount": round(pays[1]["amount"] - 2453, 2)}})

        # ---- Plot B: paid + verified receipt (for revision UI) ----
        uB = avail[1]
        gtB = round(sum(float(uB["data"].get(k) or 0) for k in cks), 2)
        a = round(gtB * 0.4, 2); b = round(gtB * 0.35, 2); cc = round(gtB - a - b, 2)
        sched = [{"due_date": "2026-07-01", "amount": a, "notes": "A"},
                 {"due_date": "2026-08-01", "amount": b, "notes": "B"},
                 {"due_date": "2026-09-01", "amount": cc, "notes": "C"}]
        r = await c.post(f"{API}/api/units/{uB['unit_id']}/sell", headers=ps, json={
            "buyer_name": "UI Paid", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gtB, "booking_amount": a, "schedule": sched})
        assert r.status_code == 200, r.text
        pays = await db.payments.find({"unit_id": uB["unit_id"]}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        pA = pays[0]
        r = await c.post(f"{API}/api/payments/{pA['payment_id']}/receipt", headers=ps,
                         json={"amount": round(a * 0.5, 2), "date": "2026-07-02", "mode": "neft", "head": "BSP Collection"})
        assert r.status_code == 200, r.text
        pA2 = await db.payments.find_one({"payment_id": pA["payment_id"]}, {"_id": 0})
        rcid = pA2["receipts"][0]["receipt_id"]
        r = await c.post(f"{API}/api/payments/{pA['payment_id']}/receipts/{rcid}/verify", headers=ac,
                         json={"decision": "yes"})
        assert r.status_code == 200, r.text
        print(f"SEEDED mismatch_plot={uA['plot_number']} paid_plot={uB['plot_number']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup())
    else:
        asyncio.run(seed())
