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
        unit = await db.units.find_one({"project_id": proj["project_id"], "status": "available",
                                        "$expr": {"$gt": [{"$size": {"$objectToArray": "$data"}}, 0]}})
        uid = unit["unit_id"]
        gt = round(sum(float(unit["data"].get(k) or 0) for k in cks), 2)
        a, b = round(gt * 0.4, 2), round(gt * 0.35, 2)
        cc = round(gt - a - b, 2)
        sched = [{"due_date": "2026-07-01", "amount": a, "notes": "A"},
                 {"due_date": "2026-08-01", "amount": b, "notes": "B"},
                 {"due_date": "2026-09-01", "amount": cc, "notes": "C"}]
        r = await c.post(f"{API}/api/units/{uid}/sell", headers=ps, json={
            "buyer_name": "Rev Test", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gt, "booking_amount": a, "schedule": sched})
        assert r.status_code == 200, r.text
        pays = await db.payments.find({"unit_id": uid}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        pA, pB, pC = pays

        # record + verify a receipt on A (pay a partial of A)
        rec_amt = round(a * 0.5, 2)
        r = await c.post(f"{API}/api/payments/{pA['payment_id']}/receipt", headers=ps,
                         json={"amount": rec_amt, "date": "2026-07-02", "mode": "neft", "head": "BSP Collection"})
        assert r.status_code == 200, r.text
        pA2 = await db.payments.find_one({"payment_id": pA["payment_id"]}, {"_id": 0})
        rcid = pA2["receipts"][0]["receipt_id"]
        r = await c.post(f"{API}/api/payments/{pA['payment_id']}/receipts/{rcid}/verify", headers=ac,
                         json={"decision": "yes"})
        assert r.status_code == 200, r.text

        # 1) edit a NON-paid instalment (swap amounts between B and C, keep total) -> no revision
        r = await c.put(f"{API}/api/units/{uid}/schedule", headers=ps, json={"installments": [
            {"payment_id": pA["payment_id"], "due_date": "2026-07-01", "amount": a, "notes": "A"},
            {"payment_id": pB["payment_id"], "due_date": "2026-08-01", "amount": cc, "notes": "B"},
            {"payment_id": pC["payment_id"], "due_date": "2026-09-01", "amount": b, "notes": "C"},
        ]})
        print("edit non-paid:", r.status_code, "revision_raised=", r.json().get("revision_raised"))
        assert r.json().get("revision_raised") is False

        # 2) edit the PAID instalment A (change its due date, keep amount==a so total stays GT) -> revision
        r = await c.put(f"{API}/api/units/{uid}/schedule", headers=ps, json={"installments": [
            {"payment_id": pA["payment_id"], "due_date": "2026-07-15", "amount": a, "notes": "A (revised)"},
            {"payment_id": pB["payment_id"], "due_date": "2026-08-01", "amount": cc, "notes": "B"},
            {"payment_id": pC["payment_id"], "due_date": "2026-09-01", "amount": b, "notes": "C"},
        ]})
        print("edit paid:", r.status_code, "revision_raised=", r.json().get("revision_raised"))
        assert r.json().get("revision_raised") is True

        # accounts see the pending revision
        r = await c.get(f"{API}/api/schedule-revisions", headers=ac, params={"status": "pending_review"})
        revs = [x for x in r.json() if x["unit_id"] == uid]
        print("pending revisions:", len(revs), "affected:", revs[0]["affected"][0]["notes"] if revs else None)
        assert len(revs) == 1
        rev = revs[0]
        assert len(rev["affected"]) == 1 and rev["affected"][0]["verified"] == rec_amt

        # post_sales cannot list revisions (403)
        r = await c.get(f"{API}/api/schedule-revisions", headers=ps)
        print("post_sales list revisions:", r.status_code)
        assert r.status_code == 403

        # approve it
        r = await c.post(f"{API}/api/schedule-revisions/{rev['revision_id']}/review", headers=ac,
                         json={"note": "Checked, ok"})
        print("approve:", r.status_code)
        assert r.status_code == 200
        r = await c.get(f"{API}/api/schedule-revisions", headers=ac, params={"status": "approved"})
        assert any(x["revision_id"] == rev["revision_id"] for x in r.json())
        # double approve -> 400
        r = await c.post(f"{API}/api/schedule-revisions/{rev['revision_id']}/review", headers=ac, json={})
        print("double approve:", r.status_code)
        assert r.status_code == 400

        # cleanup
        await db.payments.delete_many({"unit_id": uid})
        await db.schedule_logs.delete_many({"unit_id": uid})
        await db.schedule_revisions.delete_many({"unit_id": uid})
        await db.units.update_one({"unit_id": uid}, {"$set": {"status": "available"},
            "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "", "final_price": "",
                       "booking_amount": "", "sold_by": "", "sold_at": ""}})
        print("CLEANED sold:", await db.units.count_documents({"status": "sold"}),
              "payments:", await db.payments.count_documents({}),
              "revisions:", await db.schedule_revisions.count_documents({}))
        print("ALL PASS")


asyncio.run(main())
