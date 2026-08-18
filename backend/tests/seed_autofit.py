"""Seed a mismatched sold plot for UI testing. Prints plot_number + unit_id + grand_total on success."""
import os, asyncio, httpx, json
from motor.motor_asyncio import AsyncIOMotorClient

API = os.popen("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2").read().strip()
MONGO = os.popen("grep MONGO_URL /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')
DBN = os.popen("grep DB_NAME /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')


async def main():
    db = AsyncIOMotorClient(MONGO)[DBN]
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{API}/api/auth/login", json={"phone": "9000000001", "password": "Pass@123"})
        ps = r.json()["access_token"]
        H = {"Authorization": f"Bearer {ps}"}
        proj = await db.projects.find_one({"name": {"$regex": "Central Vista", "$options": "i"}})
        charge_keys = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
        unit = await db.units.find_one({"project_id": proj["project_id"], "status": "available",
                                        "$expr": {"$gt": [{"$size": {"$objectToArray": "$data"}}, 0]}})
        gt = round(sum(float(unit["data"].get(k) or 0) for k in charge_keys), 2)
        half = round(gt / 2, 2)
        sched = [
            {"due_date": "2026-07-01", "amount": half, "notes": "Booking"},
            {"due_date": "2026-09-01", "amount": round(gt - half, 2), "notes": "Balance"},
        ]
        r = await c.post(f"{API}/api/units/{unit['unit_id']}/sell", headers=H, json={
            "buyer_name": "AutoFit UI Test", "buyer_contact": "", "sale_date": "2026-06-01",
            "final_price": gt, "booking_amount": half, "schedule": sched})
        assert r.status_code == 200, r.text
        pays = await db.payments.find({"unit_id": unit["unit_id"]}, {"_id": 0}).to_list(10)
        pays.sort(key=lambda x: x["seq"])
        target = pays[1]
        await db.payments.update_one({"payment_id": target["payment_id"]},
                                     {"$set": {"amount": round(target["amount"] - 2453, 2)}})
        info = {"unit_id": unit["unit_id"], "plot_number": unit["plot_number"],
                "grand_total": gt, "project_id": unit["project_id"], "diff": 2453}
        with open("/tmp/seed_info.json", "w") as f:
            json.dump(info, f)
        print(json.dumps(info))

asyncio.run(main())
