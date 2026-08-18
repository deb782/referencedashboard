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
        ps = await login(c, "9000000001", "Pass@123")
        H = {"Authorization": f"Bearer {ps}"}
        # pick an available CVF plot with charge components
        proj = await db.projects.find_one({"name": {"$regex": "Central Vista", "$options": "i"}})
        charge_keys = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        unit = await db.units.find_one({"project_id": proj["project_id"], "status": "available",
                                        "$expr": {"$gt": [{"$size": {"$objectToArray": "$data"}}, 0]}})
        gt = round(sum(float(unit["data"].get(k) or 0) for k in charge_keys), 2)
        print("plot", unit["plot_number"], "grand total", gt)
        assert gt > 0
        # book with a valid schedule that sums to gt (2 instalments)
        half = round(gt / 2, 2)
        sched = [
            {"due_date": "2026-07-01", "amount": half, "notes": "Booking"},
            {"due_date": "2026-09-01", "amount": round(gt - half, 2), "notes": "Balance"},
        ]
        r = await c.post(f"{API}/api/units/{unit['unit_id']}/sell", headers=H, json={
            "buyer_name": "AutoFit Test", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gt, "booking_amount": half, "schedule": sched})
        print("sell:", r.status_code, r.text[:120])
        assert r.status_code == 200

        # tamper: reduce the 2nd payment by 2453 to create a mismatch (schedule < grand total)
        pays = await db.payments.find({"unit_id": unit["unit_id"]}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        target = pays[1]
        await db.payments.update_one({"payment_id": target["payment_id"]},
                                     {"$set": {"amount": round(target["amount"] - 2453, 2)}})

        # mismatched-plots should now list this plot
        r = await c.get(f"{API}/api/mismatched-plots", headers=H)
        data = r.json()
        print("mismatched count:", data["count"], "diff:",
              [i["difference"] for i in data["items"] if i["unit_id"] == unit["unit_id"]])
        item = next(i for i in data["items"] if i["unit_id"] == unit["unit_id"])
        assert abs(item["difference"] - 2453) < 1, item["difference"]

        # auto-fit onto the 2nd instalment
        r = await c.post(f"{API}/api/units/{unit['unit_id']}/auto-fit-schedule", headers=H,
                         json={"payment_id": target["payment_id"]})
        print("auto-fit:", r.status_code, r.json())
        assert r.status_code == 200

        # now schedule should equal grand total => no longer mismatched
        r = await c.get(f"{API}/api/mismatched-plots", headers=H)
        still = [i for i in r.json()["items"] if i["unit_id"] == unit["unit_id"]]
        print("still mismatched:", len(still))
        assert len(still) == 0

        # auto-fit again should 400 (already matches)
        r = await c.post(f"{API}/api/units/{unit['unit_id']}/auto-fit-schedule", headers=H,
                         json={"payment_id": target["payment_id"]})
        print("auto-fit-again:", r.status_code, r.text[:100])
        assert r.status_code == 400

        # cleanup: revert plot to available, delete payments + logs
        await db.payments.delete_many({"unit_id": unit["unit_id"]})
        await db.schedule_logs.delete_many({"unit_id": unit["unit_id"]})
        await db.units.update_one({"unit_id": unit["unit_id"]}, {
            "$set": {"status": "available"},
            "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                       "final_price": "", "booking_amount": "", "sold_by": "", "sold_at": ""}})
        print("CLEANED. sold left:", await db.units.count_documents({"status": "sold"}),
              "payments left:", await db.payments.count_documents({}))
        print("ALL PASS")


asyncio.run(main())
