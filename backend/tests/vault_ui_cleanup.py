import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')
CVF="proj_01d7e89ba838"; VV="proj_53fb360c1f0a"; UID="unit_0c43bec88847"
async def main():
    db = AsyncIOMotorClient(M)[D]
    await db.payments.delete_many({"unit_id": UID})
    await db.schedule_logs.delete_many({"unit_id": UID})
    await db.schedule_revisions.delete_many({"unit_id": UID})
    await db.units.update_one({"unit_id": UID}, {"$set":{"status":"available"},
        "$unset":{"buyer_name":"","buyer_contact":"","sale_date":"","final_price":"","booking_amount":"","sold_by":"","sold_at":"","vault":""}})
    cvf_c = await db.units.count_documents({"project_id": CVF})
    cvf_sold = await db.units.count_documents({"project_id": CVF, "status":"sold"})
    vv_c = await db.units.count_documents({"project_id": VV})
    payments = await db.payments.count_documents({"project_id": CVF})
    revs = await db.schedule_revisions.count_documents({"project_id": CVF})
    proj = await db.projects.find_one({"project_id": CVF},{"_id":0})
    has_vcfg = bool(proj.get("vault_config"))
    print(f"CVF total={cvf_c} sold={cvf_sold} payments={payments} revs={revs} vault_config_intact={has_vcfg}")
    print(f"VV total={vv_c}")
    assert cvf_c==101 and cvf_sold==0 and vv_c==256 and has_vcfg
    print("DB CLEAN ✓")
asyncio.run(main())
