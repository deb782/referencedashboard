"""Tests for /api/units/import robust header detection (Central Vista Farms bug fix)."""
import io
import os
import csv
import pytest
import requests
from openpyxl import Workbook

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fall back to frontend/.env
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")

ADMIN_PHONE = "9999999999"
ADMIN_PASS = "Repro@123"
CVF_PROJECT = "proj_01d7e89ba838"  # Central Vista Farms


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": ADMIN_PHONE, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


created_plots = []


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post_import(auth_headers, filename, content, project_id=CVF_PROJECT):
    return requests.post(
        f"{BASE_URL}/api/units/import",
        headers=auth_headers,
        data={"project_id": project_id},
        files={"file": (filename, content,
                        "text/csv" if filename.endswith(".csv") else
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )


def _cleanup(plots):
    """Best-effort delete of the units we just created via Mongo directly."""
    try:
        from pymongo import MongoClient
        env = {}
        for line in open("/app/backend/.env"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
        cli = MongoClient(env["MONGO_URL"])
        cli[env["DB_NAME"]].units.delete_many(
            {"project_id": CVF_PROJECT, "plot_number": {"$in": list(plots)}})
    except Exception as e:
        print("cleanup failed:", e)


# ---------------- Test 1: Bug verification - varied header xlsx ----------------
def test_import_varied_header_xlsx(auth_headers):
    rows = [
        ["CENTRAL VISTA FARMS - COST SHEET"],
        [],
        ["Plot No.", "Area (Sq. Ft)", "Basic Price", "East Facing", "Hill View",
         "Corner", "Infrastructure & Dev Charges", "Legal Charges",
         "Club Membership", "Advance Maintenance", "IFMS", "Total Amount"],
        ["TCVF-101", "1200", "30,00,000", "50000", "0", "0",
         "1,20,000", "25000", "50000", "24000", "60000", "33,29,000"],
        ["TCVF-102", "1500", "37,50,000", "0", "75000", "0",
         "1,50,000", "25000", "50000", "30000", "75000", "41,55,000"],
    ]
    plots = ["TCVF-101", "TCVF-102"]
    created_plots.extend(plots)
    r = _post_import(auth_headers, "cvf_varied.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body["inserted"] == 2, body
    assert body["errors"] == [], body

    # Verify persistence + numeric parsing
    lst = requests.get(f"{BASE_URL}/api/units", headers=auth_headers,
                       params={"project_id": CVF_PROJECT}, timeout=15).json()
    by_plot = {u["plot_number"]: u for u in lst}
    assert "TCVF-101" in by_plot
    u = by_plot["TCVF-101"]
    assert u["area_sqft"] == 1200
    assert u["other_charges"]["bsp"] == 3000000, u["other_charges"]
    assert u["other_charges"]["infra_dev"] == 120000


# ---------------- Test 2: CSV support ----------------
def test_import_csv(auth_headers):
    header = ["Plot", "Area", "Basic Sale Price", "East Facing", "Hill View",
              "Corner", "Infrastructure", "Legal", "Club", "Maintenance",
              "IFMS", "Grand Total"]
    row = ["TCVF-CSV1", "1000", "\"25,00,000\"", "0", "0", "0",
           "\"1,00,000\"", "20000", "40000", "20000", "50000",
           "\"27,30,000\""]
    # Build proper CSV with quoting
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerow(["TCVF-CSV1", "1000", "25,00,000", "0", "0", "0",
                "1,00,000", "20000", "40000", "20000", "50000", "27,30,000"])
    content = buf.getvalue().encode("utf-8")
    created_plots.append("TCVF-CSV1")
    r = _post_import(auth_headers, "cvf.csv", content)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body["inserted"] == 1, body
    assert body["errors"] == [], body

    lst = requests.get(f"{BASE_URL}/api/units", headers=auth_headers,
                       params={"project_id": CVF_PROJECT}, timeout=15).json()
    by_plot = {u["plot_number"]: u for u in lst}
    assert "TCVF-CSV1" in by_plot
    assert by_plot["TCVF-CSV1"]["other_charges"]["bsp"] == 2500000


# ---------------- Test 3: Classic header regression ----------------
def test_import_classic_header_xlsx(auth_headers):
    rows = [
        ["VACATION VILLAGE - RERA COST SHEET"],
        ["UNIT NO.", "EXTENT (SFT)", "Basic Sale Price", "East Facing PLC",
         "Hill View PLC", "CORNER PLC", "Infrastructure & development charges",
         "Legal and Administrative Charges", "Club membership",
         "Advance maintenance Charges for 2 years", "IFMS", "Grand Total"],
        ["TCLASSIC-1", 1000, 2500000, 0, 50000, 0, 100000, 20000, 40000,
         20000, 50000, 2780000],
    ]
    created_plots.append("TCLASSIC-1")
    r = _post_import(auth_headers, "classic.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert body["inserted"] == 1, body


# ---------------- Test 4: Negative - no unit column ----------------
def test_import_no_header_returns_400(auth_headers):
    rows = [["Name", "Value"], ["foo", "1"], ["bar", "2"]]
    r = _post_import(auth_headers, "bad.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
    detail = r.json().get("detail", "")
    assert "header" in detail.lower(), f"detail should mention header: {detail}"


def test_zzz_cleanup(auth_headers):
    """Runs last (alphabetical) to remove test units."""
    _cleanup(set(created_plots))
