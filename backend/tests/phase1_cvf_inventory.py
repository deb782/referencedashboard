"""Phase 1 (CVF only): retag PLC columns -> charge, backfill PLC values from the
inventory sheet, verify Grand Total == NET PAYABLE, and add the 54 missing farms
as AVAILABLE plots with zero values so CVF shows all 101. VV is never touched.

Run:  python phase1_cvf_inventory.py            (dry-run, verify only)
      python phase1_cvf_inventory.py apply       (write changes)
"""
import os, sys, asyncio, openpyxl
from motor.motor_asyncio import AsyncIOMotorClient

APPLY = len(sys.argv) > 1 and sys.argv[1] == "apply"
INV = "/tmp/cvf_inv.xlsx"
CVF = "proj_01d7e89ba838"
PLC_KEYS = ["east_facing_plc", "corner_plc", "cv_facing_plc", "2_or_more_plcs"]
# inventory 0-based col indices: EAST=6, CORNER=7, CV=8, 2+=9 ; FARM#=0 ; NET PAYABLE=23
INV_COL = {"east_facing_plc": 6, "corner_plc": 7, "cv_facing_plc": 8, "2_or_more_plcs": 9}
NET_COL = 23
M = os.popen("grep MONGO_URL /app/backend/.env|cut -d= -f2").read().strip().strip('"')
D = os.popen("grep DB_NAME /app/backend/.env|cut -d= -f2").read().strip().strip('"')


def num(v):
    try: return round(float(v or 0), 2)
    except Exception: return 0.0


def load_inventory():
    ws = openpyxl.load_workbook(INV, data_only=True).active
    rows = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] in (None, ""):
            continue
        farm = str(int(r[0]))
        rows[farm] = {k: num(r[INV_COL[k]]) for k in PLC_KEYS} | {"net": num(r[NET_COL])}
    return rows


async def main():
    db = AsyncIOMotorClient(M)[D]
    inv = load_inventory()
    print(f"inventory rows: {len(inv)}")

    proj = await db.projects.find_one({"project_id": CVF}, {"_id": 0})
    charge_keys = [c["key"] for c in proj["columns"] if c.get("tag") == "charge"]
    charge_keys_after = charge_keys + [k for k in PLC_KEYS if k not in charge_keys]
    print("charge cols now:", len(charge_keys), "-> after retag:", len(charge_keys_after))

    units = await db.units.find({"project_id": CVF}, {"_id": 0}).to_list(500)
    print(f"existing CVF units: {len(units)}")

    # verify: sum(charge incl PLC) == inventory NET PAYABLE (the true total)
    ok = bad = 0
    for u in units:
        farm = str(u["plot_number"])
        data = dict(u.get("data") or {})
        src = inv.get(farm, {})
        for k in PLC_KEYS:
            data[k] = src.get(k, num(data.get(k)))
        gt = round(sum(num(data.get(k)) for k in charge_keys_after), 2)
        net = num(src.get("net"))
        if abs(gt - net) <= 1:
            ok += 1
        else:
            bad += 1
            print(f"  MISMATCH farm {farm}: grand={gt} inv_net={net} diff={round(gt-net,2)}")
    print(f"verify vs inventory NET PAYABLE: {ok} match, {bad} mismatch")

    present = {str(u["plot_number"]) for u in units}
    missing = [n for n in range(1, 102) if str(n) not in present]
    print(f"missing farms to add ({len(missing)}):", missing)

    if not APPLY:
        print("\nDRY-RUN only. Re-run with 'apply' to write.")
        return

    # 1) retag PLC columns -> charge
    cols = proj["columns"]
    for c in cols:
        if c["key"] in PLC_KEYS:
            c["tag"] = "charge"
    await db.projects.update_one({"project_id": CVF}, {"$set": {"columns": cols}})
    print("retagged PLC columns -> charge")

    # 2) backfill PLC values + refresh stored net_payable + resync stored total
    for u in units:
        farm = str(u["plot_number"])
        data = dict(u.get("data") or {})
        src = inv.get(farm, {})
        for k in PLC_KEYS:
            data[k] = src.get(k, num(data.get(k)))
        if src.get("net"):
            data["net_payable"] = num(src["net"])
        gt = round(sum(num(data.get(k)) for k in charge_keys_after), 2)
        await db.units.update_one({"unit_id": u["unit_id"]},
                                  {"$set": {"data": data, "total": gt}})
    print(f"backfilled PLC + refreshed net_payable + resynced total on {len(units)} units")

    # 3) add missing farms as AVAILABLE with zero values
    all_keys = [c["key"] for c in cols if c.get("tag") in ("charge", "total", "area", "reference")]
    import uuid
    added = 0
    for n in missing:
        data = {k: 0 for k in all_keys}
        await db.units.insert_one({
            "unit_id": "unit_" + uuid.uuid4().hex[:12], "project_id": CVF,
            "plot_number": str(n), "area_sqft": 0, "area": 0, "plc_details": "",
            "other_charges": 0, "status": "available", "data": data, "total": 0,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
        added += 1
    print(f"added {added} available plots")
    total = await db.units.count_documents({"project_id": CVF})
    print(f"CVF total units now: {total}")
    # VV sanity — must be unchanged
    vv = await db.units.count_documents({"project_id": "proj_53fb360c1f0a"})
    print(f"VV units (must be 256): {vv}")


asyncio.run(main())
