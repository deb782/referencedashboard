"""CVF real-format importer tests (FARM#/NET PAYABLE/CV FACING PLC/2 OR MORE PLCs etc).

- Creates a scratch project 'TEST_CVF_Import' to avoid disturbing real data.
- Verifies CVF-format mapping, existing 47 units in proj_01d7e89ba838, idempotency,
  regression on classic/CSV formats, and the negative-header case.
- Cleans up scratch project + units via Mongo (no unit DELETE API exists).
"""
import io
import os
import csv
import pytest
import requests
from openpyxl import Workbook

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_PHONE = "9999999999"
ADMIN_PASS = "Repro@123"
REAL_CVF_PROJECT = "proj_01d7e89ba838"

CVF_HEADER = [
    "FARM#", "EXTENT (SFT)", "BSP", "GUIDANCE VALUE",
    "DEVELOPMENT CHARGE", "18% GST",
    "EAST FACING PLC", "CORNER PLC", "CV FACING PLC", "2 OR MORE PLCs",
    "LEGAL FEE", "18% GST",
    "ELECTRICITY INFRASTRUCTURE CHARGES", "18% GST",
    "KHATA & REGISTRATION CHARGES", "18% GST",
    "ADVANCE MAINTENANCE-2 YEARS", "18% GST",
    "Club Membership", "18% GST of Club Membership",
    "IFMS", "SINKING FUND", "STAMP DUTY", "NET PAYABLE",
]

# Two data rows. Row 1 = FARM# 32 (the canonical assertion target).
CVF_ROWS = [
    ["32", 7911.5, 5933625, 500000, 200000, 36000,
     0, 0, 0, 445021.875,
     10000, 1800,
     50000, 9000,
     40000, 7200,
     30000, 5400,
     100000, 18000,
     50000, 25000, 300000, 8079622.43],
    ["33", 8000.0, 6000000, 510000, 210000, 37800,
     0, 100000, 0, 0,
     10000, 1800,
     50000, 9000,
     40000, 7200,
     30000, 5400,
     100000, 18000,
     50000, 25000, 305000, 7500000.00],
]


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": ADMIN_PHONE, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def scratch_project(admin_headers):
    """Create a temp project 'TEST_CVF_Import', delete at teardown."""
    r = requests.post(f"{BASE_URL}/api/projects", headers=admin_headers,
                      json={"name": "TEST_CVF_Import", "location": "TEST"}, timeout=15)
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    pid = r.json()["project_id"]
    yield pid
    # Teardown - delete project + its units via API
    requests.delete(f"{BASE_URL}/api/projects/{pid}",
                    headers=admin_headers, timeout=15)


def _post_import(admin_headers, project_id, filename, content):
    return requests.post(
        f"{BASE_URL}/api/units/import",
        headers=admin_headers,
        data={"project_id": project_id},
        files={"file": (filename, content,
                        "text/csv" if filename.endswith(".csv") else
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )


# ------------------ TEST 1: CVF real-format import into scratch project ------
def test_cvf_realformat_import(admin_headers, scratch_project):
    rows = [CVF_HEADER] + CVF_ROWS
    r = _post_import(admin_headers, scratch_project,
                     "cvf_realformat.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert "Could not find a header row" not in str(body)
    assert body["inserted"] == len(CVF_ROWS), body
    assert body["errors"] == [], body

    # Verify FARM# 32 data
    lst = requests.get(f"{BASE_URL}/api/units", headers=admin_headers,
                       params={"project_id": scratch_project}, timeout=15).json()
    by_plot = {u["plot_number"]: u for u in lst}
    assert "32" in by_plot, f"plot 32 missing; got {list(by_plot)}"
    u = by_plot["32"]
    assert u["area_sqft"] == 7911.5, u
    oc = u["other_charges"]
    assert oc["bsp"] == 5933625, oc
    assert oc["sheet_grand_total"] == 8079622.43, oc
    plc = u["plc_details"]
    assert plc["multi_plc"] == 445021.875, plc


# ------------------ TEST 2: existing CVF data (47 units) intact --------------
def test_existing_cvf_data_intact(admin_headers):
    lst = requests.get(f"{BASE_URL}/api/units", headers=admin_headers,
                       params={"project_id": REAL_CVF_PROJECT}, timeout=15).json()
    assert isinstance(lst, list)
    assert len(lst) == 47, f"expected 47 CVF units, got {len(lst)}"
    for u in lst:
        assert str(u["plot_number"]).lstrip("-").isdigit(), \
            f"non-numeric plot_number: {u.get('plot_number')}"
        assert (u.get("other_charges") or {}).get("sheet_grand_total", 0) > 0, \
            f"unit {u['plot_number']} has no sheet_grand_total"
    by_plot = {u["plot_number"]: u for u in lst}
    assert "32" in by_plot, f"plot 32 missing from CVF"
    assert by_plot["32"]["other_charges"]["sheet_grand_total"] == 8079622.43


# ------------------ TEST 3: idempotent re-import (no duplicates) -------------
def test_cvf_reimport_is_idempotent(admin_headers, scratch_project):
    rows = [CVF_HEADER] + CVF_ROWS
    r = _post_import(admin_headers, scratch_project,
                     "cvf_realformat.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/units", headers=admin_headers,
                       params={"project_id": scratch_project}, timeout=15).json()
    plots = [u["plot_number"] for u in lst]
    assert len(plots) == len(set(plots)), f"duplicates: {plots}"
    assert len(plots) == len(CVF_ROWS), f"expected {len(CVF_ROWS)} unique, got {plots}"


# ------------------ TEST 4a: classic Vacation Village header regression ------
def test_regression_classic_vv_header(admin_headers, scratch_project):
    rows = [
        ["VACATION VILLAGE"],
        ["UNIT NO.", "EXTENT (SFT)", "Basic Sale Price",
         "Hill View PLC", "CORNER PLC", "Grand Total"],
        ["TVV-1", 1000, 2500000, 50000, 0, 2780000],
        ["TVV-2", 1200, 3000000, 0, 40000, 3200000],
    ]
    r = _post_import(admin_headers, scratch_project,
                     "vv_classic.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    assert r.json()["inserted"] == 2, r.json()


# ------------------ TEST 4b: CSV format regression ---------------------------
def test_regression_csv(admin_headers, scratch_project):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Plot", "Area", "Basic Sale Price", "Hill View PLC",
                "Corner", "Infrastructure", "Legal", "Grand Total"])
    w.writerow(["TCSV-1", "1000", "25,00,000", "0", "0", "1,00,000",
                "20000", "27,30,000"])
    r = _post_import(admin_headers, scratch_project,
                     "regress.csv", buf.getvalue().encode("utf-8"))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    assert r.json()["inserted"] == 1, r.json()


# ------------------ TEST 4c: title row + 'Plot No.' / 'Total Amount' ---------
def test_regression_title_plotno_totalamount(admin_headers, scratch_project):
    rows = [
        ["CENTRAL VISTA FARMS - COST SHEET"],
        [],
        ["Plot No.", "Area (Sq. Ft)", "Basic Price", "Hill View",
         "Infrastructure & Dev Charges", "Total Amount"],
        ["TTITLE-1", 1200, 3000000, 50000, 120000, 3329000],
    ]
    r = _post_import(admin_headers, scratch_project,
                     "title.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    assert r.json()["inserted"] == 1, r.json()


# ------------------ TEST 5: negative — no unit column -> 400 -----------------
def test_negative_no_unit_column(admin_headers, scratch_project):
    rows = [["Name", "Value"], ["foo", 1], ["bar", 2]]
    r = _post_import(admin_headers, scratch_project,
                     "bad.xlsx", _xlsx_bytes(rows))
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
    detail = r.json().get("detail", "").lower()
    assert "header" in detail, f"detail should mention header: {detail}"
