"""Phase-1 backend tests: dynamic inventory (preview/commit), add/edit plot,
dashboards (by_project + consolidated), admin reset-password, sell schedule."""
import io, os, json, csv
import pytest, requests
from openpyxl import Workbook

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
ADMIN_PHONE = "9513242807"
ADMIN_PASS = "Repro@123"
VV = "proj_53fb360c1f0a"   # Vacation Village (no schema yet)
CVF = "proj_01d7e89ba838"  # Central Vista Farms (schema saved, 47 plots)

_created_users, _added_plots = [], []  # (uid,) and (unit_id,)


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": ADMIN_PHONE, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def _xlsx(rows):
    wb = Workbook(); ws = wb.active
    for r in rows: ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


# ---------- 1. Preview endpoint ------------------------------------------------
def test_preview_returns_columns_with_suggested_tags(h):
    rows = [
        ["UNIT NO.", "EXTENT (SFT)", "Basic Sale Price", "Legal", "Club", "IFMS", "Grand Total"],
        ["V-1", 1000, 2500000, 20000, 40000, 50000, 2610000],
        ["V-2", 1200, 3000000, 20000, 40000, 50000, 3110000],
        ["V-3", 1400, 3500000, 20000, 40000, 50000, 3610000],
    ]
    r = requests.post(f"{BASE_URL}/api/units/preview", headers=h,
                      data={"project_id": VV},
                      files={"file": ("vv.xlsx", _xlsx(rows),
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                      timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 3
    tags = {c["label"]: c["tag"] for c in body["columns"]}
    assert tags["UNIT NO."] == "plot_id"
    assert tags["EXTENT (SFT)"] == "area"
    assert tags["Grand Total"] == "total"
    # numeric charges default to charge
    assert tags["Basic Sale Price"] == "charge"
    assert tags["Legal"] == "charge"
    for c in body["columns"]:
        assert "key" in c and "col_index" in c and "samples" in c


# ---------- 2. Commit endpoint -------------------------------------------------
def test_commit_requires_plot_id_tag(h):
    rows = [["A", "B"], [1, 2]]
    mapping = json.dumps([{"key": "a", "label": "A", "col_index": 0, "tag": "charge"},
                          {"key": "b", "label": "B", "col_index": 1, "tag": "charge"}])
    r = requests.post(f"{BASE_URL}/api/units/commit", headers=h,
                      data={"project_id": VV, "mapping": mapping},
                      files={"file": ("bad.xlsx", _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                      timeout=30)
    assert r.status_code == 400, r.text
    assert "plot" in r.json().get("detail", "").lower()


def test_commit_vacation_village_end_to_end(h):
    # Use plot numbers that won't collide with existing VV plots 1..256 -> use big/prefixed keys
    rows = [
        ["UNIT NO.", "EXTENT (SFT)", "Basic Sale Price", "Legal", "Club", "IFMS", "Grand Total"],
        ["TVV-A1", 1000, 2500000.556, 20000, 40000, 50000, 2610000.556],
        ["TVV-A2", 1200, 3000000, 20000, 40000, 50000, 3110000],
        ["TVV-A3", 1400, 3500000, 20000, 40000, 50000, 3610000],
    ]
    content = _xlsx(rows)
    # first preview to get column keys/indices
    pr = requests.post(f"{BASE_URL}/api/units/preview", headers=h,
                       data={"project_id": VV},
                       files={"file": ("vv2.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                       timeout=30)
    assert pr.status_code == 200
    cols = pr.json()["columns"]
    # ensure Grand Total tagged total, area tagged area (defaults already), rest charge
    r = requests.post(f"{BASE_URL}/api/units/commit", headers=h,
                      data={"project_id": VV, "mapping": json.dumps(cols)},
                      files={"file": ("vv2.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                      timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inserted"] + body["updated"] >= 3
    assert body["errors"] == []
    # schema saved on project
    projs = requests.get(f"{BASE_URL}/api/projects", headers=h, timeout=15).json()
    vv = next(p for p in projs if p["project_id"] == VV)
    assert vv.get("columns"), "Project.columns not persisted"
    labels = {c["label"] for c in vv["columns"]}
    assert {"UNIT NO.", "EXTENT (SFT)", "Grand Total"}.issubset(labels)

    # GET /units returns generic data/area/total with 2dp rounding
    units = requests.get(f"{BASE_URL}/api/units", headers=h,
                        params={"project_id": VV}, timeout=15).json()
    by = {u["plot_number"]: u for u in units}
    assert "TVV-A1" in by
    u = by["TVV-A1"]
    assert u["area"] == 1000.0
    assert u["total"] == 2610000.56  # 2dp rounding of .556
    assert isinstance(u.get("data"), dict) and len(u["data"]) > 0
    # BSP rounded to 2dp inside data
    bsp_key = next(c["key"] for c in vv["columns"] if c["label"] == "Basic Sale Price")
    assert u["data"][bsp_key] == 2500000.56


# ---------- 3. Ascending numeric sort -----------------------------------------
def test_units_sorted_numerically_ascending(h):
    rows = requests.get(f"{BASE_URL}/api/units", headers=h,
                       params={"project_id": CVF}, timeout=15).json()
    # first 5 plots must be numerically ascending
    def num(pn):
        import re
        m = re.match(r"^\s*(\d+)", str(pn))
        return int(m.group(1)) if m else 10**9
    nums = [num(u["plot_number"]) for u in rows[:10]]
    assert nums == sorted(nums), nums


# ---------- 4. CVF pivots present in dashboard --------------------------------
def test_dashboard_admin_has_by_project_and_consolidated(h):
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "by_project" in d and "consolidated" in d
    projs = {p["project_id"]: p for p in d["by_project"]}
    assert CVF in projs and VV in projs
    cvf = projs[CVF]
    assert cvf["total_units"] == 47
    assert len(cvf["pivots"]) >= 10, cvf["pivots"]
    # BSP sum ~27.68 Cr
    bsp = next((p for p in cvf["pivots"] if "bsp" in p["label"].lower() or "basic" in p["label"].lower()), None)
    assert bsp is not None
    assert 2.5e8 < bsp["sum_all"] < 3.0e8, bsp
    # consolidated fields
    c = d["consolidated"]
    for k in ("total_units", "available", "sold", "booked_value", "received_total", "pending_total"):
        assert k in c


# ---------- 5. Add / Edit plot ------------------------------------------------
def test_add_plot_and_edit_plot_and_duplicate(h):
    # get project column schema of CVF
    projs = requests.get(f"{BASE_URL}/api/projects", headers=h, timeout=15).json()
    cvf = next(p for p in projs if p["project_id"] == CVF)
    cols = cvf["columns"]
    # build data dict: numeric where numeric-tag, empty for reference/ignore text
    data = {}
    for c in cols:
        if c["tag"] == "plot_id": continue
        if c["tag"] in ("charge", "total", "area", "reference"):
            data[c["key"]] = 111.117  # -> 111.12 (avoid banker rounding boundary)
        else:
            data[c["key"]] = "x"
    plot_no = "TEST_9001"
    r = requests.post(f"{BASE_URL}/api/projects/{CVF}/plots", headers=h,
                      json={"plot_number": plot_no, "data": data}, timeout=15)
    assert r.status_code == 200, r.text
    unit_id = r.json()["unit_id"]
    _added_plots.append(unit_id)
    # 2dp rounding & area/total derived
    got = r.json()
    numeric_keys = [c["key"] for c in cols if c["tag"] in ("charge", "total", "area", "reference")]
    for k in numeric_keys:
        assert got["data"][k] == 111.12, (k, got["data"][k])
    area_key = next((c["key"] for c in cols if c["tag"] == "area"), None)
    total_key = next((c["key"] for c in cols if c["tag"] == "total"), None)
    if area_key: assert got["area"] == 111.12
    if total_key: assert got["total"] == 111.12

    # duplicate should 400
    dup = requests.post(f"{BASE_URL}/api/projects/{CVF}/plots", headers=h,
                       json={"plot_number": plot_no, "data": data}, timeout=15)
    assert dup.status_code == 400

    # edit
    data2 = {**data}
    if numeric_keys:
        data2[numeric_keys[0]] = 222.22
    edit = requests.patch(f"{BASE_URL}/api/units/{unit_id}", headers=h,
                         json={"plot_number": plot_no, "data": data2}, timeout=15)
    assert edit.status_code == 200, edit.text
    # verify
    units = requests.get(f"{BASE_URL}/api/units", headers=h,
                       params={"project_id": CVF}, timeout=15).json()
    u = next(u for u in units if u["unit_id"] == unit_id)
    assert u["data"][numeric_keys[0]] == 222.22


# ---------- 6. Admin reset password -------------------------------------------
def test_admin_reset_password(h):
    # create throwaway user
    uphone = "9000000001"
    r = requests.post(f"{BASE_URL}/api/users", headers=h,
                      json={"name": "TEST_ResetUser", "phone": uphone, "role": "post_sales"},
                      timeout=15)
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    _created_users.append(uid)
    # change its password to something else first via login+change? simpler: just reset
    r2 = requests.post(f"{BASE_URL}/api/users/{uid}/reset-password", headers=h, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True
    # login with phone as password
    lg = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": uphone, "password": uphone}, timeout=15)
    assert lg.status_code == 200, lg.text
    assert lg.json()["user"].get("must_reset_password") is True


# ---------- 7. Sell flow schedule (instalment name + on-possession) -----------
def test_sell_unit_with_schedule(h):
    # find an available CVF unit that is NOT our TEST_9001
    units = requests.get(f"{BASE_URL}/api/units", headers=h,
                       params={"project_id": CVF, "status": "available"}, timeout=15).json()
    unit = next(u for u in units if not str(u["plot_number"]).startswith("TEST_"))
    unit_id = unit["unit_id"]
    default_total = unit.get("total") or 1000000
    booking = 100000
    remainder = default_total - booking
    sched_a = round(remainder * 0.6, 2)
    sched_b = round(remainder - sched_a, 2)
    payload = {
        "buyer_name": "TEST_Buyer",
        "buyer_contact": "9000000099",
        "sale_date": "2026-01-15",
        "final_price": default_total,
        "booking_amount": booking,
        "schedule": [
            {"due_date": "2026-02-15", "amount": sched_a, "notes": "1st Instalment"},
            {"due_date": "On Offer of Possession", "amount": sched_b,
             "notes": "Final on Possession"},
        ],
    }
    r = requests.post(f"{BASE_URL}/api/units/{unit_id}/sell", headers=h,
                     json=payload, timeout=15)
    # Test may 200 or 422 depending on model; capture both
    assert r.status_code in (200, 201), r.text
    # verify unit now sold
    lst = requests.get(f"{BASE_URL}/api/units", headers=h,
                     params={"project_id": CVF}, timeout=15).json()
    u = next(u for u in lst if u["unit_id"] == unit_id)
    assert u["status"] == "sold"
    # payments created with notes populated
    pays = requests.get(f"{BASE_URL}/api/payments", headers=h,
                     params={"project_id": CVF}, timeout=15).json()
    mine = [p for p in pays if p.get("unit_id") == unit_id]
    assert len(mine) >= 2
    notes = [p.get("notes") for p in mine]
    assert any(n and "Instalment" in n for n in notes), notes
    dds = [p.get("due_date") for p in mine]
    assert any(d == "On Offer of Possession" for d in dds), dds


# ---------- ZZZ cleanup -------------------------------------------------------
def test_zzz_cleanup(h):
    for uid in _created_users:
        requests.delete(f"{BASE_URL}/api/users/{uid}", headers=h, timeout=10)
    # remove TEST_ plots we added to CVF
    units = requests.get(f"{BASE_URL}/api/units", headers=h,
                       params={"project_id": CVF}, timeout=15).json()
    # remove TVV-A* from VV
    vv_units = requests.get(f"{BASE_URL}/api/units", headers=h,
                       params={"project_id": VV}, timeout=15).json()
    # No DELETE unit endpoint — cleanup via Mongo direct
    try:
        from pymongo import MongoClient
        env = {}
        for line in open("/app/backend/.env"):
            if "=" in line:
                k, v = line.strip().split("=", 1); env[k] = v
        cli = MongoClient(env["MONGO_URL"])
        cli[env["DB_NAME"]].units.delete_many(
            {"project_id": CVF, "plot_number": {"$regex": "^TEST_"}})
        cli[env["DB_NAME"]].units.delete_many(
            {"project_id": VV, "plot_number": {"$regex": "^TVV-"}})
        # Un-sell CVF plot sold during sell-test and delete its test payments
        cli[env["DB_NAME"]].payments.delete_many({"buyer_contact": "9000000099"})
        cli[env["DB_NAME"]].payments.delete_many({"received_notes": {"$regex": "TEST_"}})
        cli[env["DB_NAME"]].units.update_many(
            {"project_id": CVF, "buyer_name": "TEST_Buyer"},
            {"$set": {"status": "available", "buyer_name": None,
                       "buyer_contact": None, "final_price": None,
                       "booking_amount": None, "sale_date": None,
                       "sold_at": None, "sold_by": None}})
        # also delete any payments still tied to the un-sold plot
        cli[env["DB_NAME"]].payments.delete_many(
            {"project_id": CVF, "notes": {"$in": ["1st Instalment", "Final on Possession"]}})
        # restore VV to no-schema state (test artifact)
        cli[env["DB_NAME"]].projects.update_one(
            {"project_id": VV}, {"$unset": {"columns": ""}})
    except Exception as e:
        print("cleanup issue:", e)
