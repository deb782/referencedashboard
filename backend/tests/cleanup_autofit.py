"""Cleanup seeded mismatch."""
import os, asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.popen("grep MONGO_URL /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')
DBN = os.popen("grep DB_NAME /app/backend/.env | cut -d '=' -f2").read().strip().strip('"')


async def main():
    db = AsyncIOMotorClient(MONGO)[DBN]
    with open("/tmp/seed_info.json") as f:
        info = json.load(f)
    uid = info["unit_id"]
    await db.payments.delete_many({"unit_id": uid})
    await db.schedule_logs.delete_many({"unit_id": uid})
    await db.units.update_one({"unit_id": uid}, {
        "$set": {"status": "available"},
        "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                   "final_price": "", "booking_amount": "", "sold_by": "", "sold_at": ""}})
    sold = await db.units.count_documents({"status": "sold"})
    pays = await db.payments.count_documents({})
    print(f"CLEANED sold={sold} payments={pays}")

asyncio.run(main())
