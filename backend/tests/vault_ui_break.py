import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')
UID = "unit_0c43bec88847"
async def main():
    db = AsyncIOMotorClient(M)[D]
    pays = await db.payments.find({"unit_id": UID, "stream": "vault"}, {"_id":0}).to_list(50)
    print("vault instalments:", len(pays))
    p0 = pays[0]
    new_amt = round(p0["amount"] - 5000, 2)
    await db.payments.update_one({"payment_id": p0["payment_id"]}, {"$set":{"amount": new_amt}})
    print(f"Broke {p0['payment_id']} amount {p0['amount']} -> {new_amt}")
asyncio.run(main())
