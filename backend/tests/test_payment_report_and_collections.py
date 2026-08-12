"""
Backend tests for iteration 19:
- PDF Payment Report download (GET /api/units/{unit_id}/payment-report) for post_sales, admin, accounts
- Post Sales dashboard 'collections' widget payload
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or
            open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()).rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "post_sales": ("9000000001", "Pass@123"),
    "accounts":   ("9000000002", "Pass@123"),
    "admin":      ("9513242807", "Repro@123"),
}


def _login(phone, password):
    r = requests.post(f"{API}/auth/login", json={"phone": phone, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {phone}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def tokens():
    return {role: _login(p, pw) for role, (p, pw) in CREDS.items()}


@pytest.fixture(scope="session")
def demo_unit_id(tokens):
    """Find CVF Plot 32 (sold to Ravi Kumar)."""
    r = requests.get(f"{API}/units", headers={"Authorization": f"Bearer {tokens['post_sales']}"}, timeout=20)
    assert r.status_code == 200
    units = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    target = next((u for u in units if str(u.get("plot_number")) == "32" and u.get("status") == "sold"), None)
    assert target, "CVF Plot 32 (sold) not found - demo data missing"
    return target["unit_id"]


# --- PDF Payment Report ---
class TestPaymentReportPDF:
    def _check_pdf(self, resp):
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        assert resp.headers.get("content-type", "").startswith("application/pdf"), \
            f"Bad content-type: {resp.headers.get('content-type')}"
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd.lower() and ".pdf" in cd.lower(), f"Bad Content-Disposition: {cd}"
        assert resp.content[:5] == b"%PDF-", f"Body doesn't start with %PDF-: {resp.content[:20]!r}"
        assert len(resp.content) > 5000, f"PDF suspiciously small: {len(resp.content)} bytes"

    def test_post_sales_can_download(self, tokens, demo_unit_id):
        r = requests.get(f"{API}/units/{demo_unit_id}/payment-report",
                         headers={"Authorization": f"Bearer {tokens['post_sales']}"}, timeout=30)
        self._check_pdf(r)

    def test_admin_can_download(self, tokens, demo_unit_id):
        r = requests.get(f"{API}/units/{demo_unit_id}/payment-report",
                         headers={"Authorization": f"Bearer {tokens['admin']}"}, timeout=30)
        self._check_pdf(r)

    def test_accounts_can_download(self, tokens, demo_unit_id):
        r = requests.get(f"{API}/units/{demo_unit_id}/payment-report",
                         headers={"Authorization": f"Bearer {tokens['accounts']}"}, timeout=30)
        self._check_pdf(r)

    def test_unauthenticated_rejected(self, demo_unit_id):
        r = requests.get(f"{API}/units/{demo_unit_id}/payment-report", timeout=15)
        assert r.status_code in (401, 403), f"Expected auth error, got {r.status_code}"


# --- Post Sales collections widget ---
class TestCollectionsWidget:
    def test_dashboard_has_collections(self, tokens):
        r = requests.get(f"{API}/dashboard", headers={"Authorization": f"Bearer {tokens['post_sales']}"}, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "collections" in data, "post_sales dashboard missing 'collections' key"
        colls = data["collections"]
        assert isinstance(colls, list) and len(colls) >= 3, f"Expected >=3 installments, got {len(colls)}"

        # find plot 32 installments
        plot32 = [c for c in colls if str(c.get("plot_number")) == "32"]
        assert len(plot32) >= 3, f"Plot 32 should have >=3 installments, got {len(plot32)}"

        # Booking should be verified/received
        booking = next((c for c in plot32 if "booking" in (c.get("installment") or "").lower()), None)
        assert booking, f"No Booking installment found in {[c.get('installment') for c in plot32]}"
        assert booking["status"] == "received" and booking["verification"] == "verified", \
            f"Booking not received/verified: {booking}"

        # Instalment 1 - partial + awaiting
        inst1 = next((c for c in plot32 if "1" in (c.get("installment") or "") and "booking" not in (c.get("installment") or "").lower()), None)
        assert inst1, "No Instalment 1 row"
        assert inst1["awaiting"] > 0, f"Instalment 1 should have awaiting > 0: {inst1}"
        assert inst1["verification"] == "awaiting", f"Instalment 1 verification not 'awaiting': {inst1}"

        # required keys
        required = {"payment_id", "unit_id", "plot_number", "buyer_name", "installment",
                    "due_amount", "due_date", "received", "awaiting", "balance", "status", "verification"}
        for c in plot32:
            missing = required - set(c.keys())
            assert not missing, f"Missing keys {missing} in row {c}"

    def test_verified_only_counts_paid(self, tokens):
        """awaiting amount should not be counted in received."""
        r = requests.get(f"{API}/dashboard", headers={"Authorization": f"Bearer {tokens['post_sales']}"}, timeout=20)
        assert r.status_code == 200
        for c in r.json().get("collections", []):
            if c.get("awaiting", 0) > 0 and c.get("received", 0) == 0:
                # partial receipt awaiting verification: balance == due
                assert abs(c["balance"] - c["due_amount"]) < 0.5, \
                    f"Awaiting-only row should have balance==due: {c}"
