import os, asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')
CVF = "proj_01d7e89ba838"
VV = "proj_53fb360c1f0a"

async def main():
    db = AsyncIOMotorClient(M)[D]
    proj = await db.projects.find_one({"project_id": CVF}, {"_id": 0})
    cks = [x["key"] for x in proj["columns"] if x["tag"] == "charge"]
    vcfg = proj["vault_config"]
    units_all = await db.units.find({"project_id": CVF}, {"_id": 0}).to_list(500)
    avail = [u for u in units_all if u["status"] == "available" and sum(float(u["data"].get(k) or 0) for k in cks) > 0]
    target = avail[0]
    gt = round(sum(float(target["data"].get(k) or 0) for k in cks), 2)
    vv_units = await db.units.find({"project_id": VV, "status":"available"}, {"_id": 0}).to_list(500)
    out = {"uid": target["unit_id"], "plot_no": target["plot_number"], "gt": gt,
           "v_variant_id": vcfg["variants"][0]["variant_id"],
           "v_total": float(vcfg["variants"][0]["total"]),
           "vv_plot": vv_units[0]["plot_number"], "vv_uid": vv_units[0]["unit_id"],
           "cvf_count": len(units_all)}
    print(json.dumps(out))
asyncio.run(main())
