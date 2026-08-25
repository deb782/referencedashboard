"""Seed The Vault config on the Central Vista Farms project only. VV untouched."""
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

CVF = "proj_01d7e89ba838"
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')

VARIANTS = [
    {"variant_id": "7000", "label": "7000 sqft", "construction": 7750000, "gst": 1395000, "total": 9145000},
    {"variant_id": "8000", "label": "8000 sqft", "construction": 8400000, "gst": 1512000, "total": 9912000},
    {"variant_id": "8000_2br", "label": "8000 sqft (2 BR)", "construction": 9100000, "gst": 1638000, "total": 10738000},
    {"variant_id": "10000", "label": "10000 sqft", "construction": 11000000, "gst": 1980000, "total": 12980000},
]
TEMPLATE = (
    [{"label": "On Booking", "pct": 10}, {"label": "On Agreement to Sell", "pct": 10}]
    + [{"label": f"Instalment {i}", "pct": 10} for i in range(1, 8)]
    + [{"label": "On Offer of Possession", "pct": 10, "on_possession": True}]
)


async def main():
    db = AsyncIOMotorClient(M)[D]
    cfg = {"enabled": True, "variants": VARIANTS, "schedule_template": TEMPLATE}
    r = await db.projects.update_one({"project_id": CVF}, {"$set": {"vault_config": cfg}})
    print("CVF vault_config set:", r.modified_count, "variants:", len(VARIANTS), "template rows:", len(TEMPLATE))
    vv = await db.projects.find_one({"project_id": "proj_53fb360c1f0a"}, {"_id": 0, "vault_config": 1})
    print("VV vault_config (must be absent):", vv.get("vault_config", "ABSENT"))


asyncio.run(main())
