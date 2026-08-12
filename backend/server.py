"""Agrocorp Lite — a stripped-down post-sales & site-ops admin.

Roles: admin, accounts, post_sales, site_manager
No email, no cron. In-app notifications only.
"""
from __future__ import annotations

import io
import csv
import os
import uuid
import json
import math
import logging
import requests
from datetime import datetime, timezone
from typing import List, Literal, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import (
    Depends, FastAPI, File, Form, HTTPException, Header, Query, UploadFile,
)
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter
from motor.motor_asyncio import AsyncIOMotorClient
from openpyxl import load_workbook
from pymongo import InsertOne, UpdateOne
from pydantic import BaseModel, ConfigDict, EmailStr, Field

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agrocorp-lite")

# ------------------------------------------------------------------ config -
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-prod")
JWT_ALG = "HS256"
JWT_TTL_MIN = int(os.environ.get("JWT_TTL_MIN", "720"))  # 12h
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "9999999999")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@agrocorp.local")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---------------------------------------------------------- object storage -
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "agrocorp-lite"
MIME_TYPES = {
    "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    "csv": "text/csv", "txt": "text/plain",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    if resp.status_code == 404:  # dead key -> re-init once
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type},
                            data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple:
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def save_upload(file: UploadFile, folder: str, user_id: str) -> dict:
    ext = (file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "bin")
    file_id = new_id("file")
    path = f"{APP_NAME}/{folder}/{user_id}/{file_id}.{ext}"
    data = await file.read()
    ctype = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    result = put_object(path, data, ctype)
    ref = {
        "file_id": file_id, "storage_path": result["path"],
        "original_filename": file.filename, "content_type": ctype,
        "size": result.get("size", len(data)), "uploaded_by": user_id,
        "uploaded_at": now(), "is_deleted": False,
    }
    await db.files.insert_one({**ref})
    return {k: v for k, v in ref.items() if k != "_id"}

def _sanitize_nonfinite(o):
    """Recursively replace NaN/Infinity floats with None so JSON serialization
    (Starlette uses allow_nan=False) never fails on bad spreadsheet data."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _sanitize_nonfinite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize_nonfinite(v) for v in o]
    return o


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(_sanitize_nonfinite(content))


app = FastAPI(title="Agrocorp Lite", default_response_class=SafeJSONResponse)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
api = APIRouter(prefix="/api")


# ---------------------------------------------------------------- helpers -
def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str) -> str:
    now_ts = datetime.now(timezone.utc)
    payload = {"sub": user_id,
               "iat": int(now_ts.timestamp()),
               "exp": int(now_ts.timestamp()) + JWT_TTL_MIN * 60}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


# ----------------------------------------------------------------- models -
Role = Literal["admin", "accounts", "post_sales", "site_manager"]


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str = Field(default_factory=lambda: new_id("usr"))
    name: str
    phone: str
    email: Optional[EmailStr] = None
    role: Role
    project_id: Optional[str] = None   # site_managers are scoped to one project
    is_active: bool = True
    must_reset_password: bool = True
    created_at: str = Field(default_factory=now)


class UserCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    role: Role
    project_id: Optional[str] = None


class LoginRequest(BaseModel):
    phone: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_id: str = Field(default_factory=lambda: new_id("proj"))
    name: str
    location: str = ""
    kind: str = ""                  # e.g. "Agricultural Plots" / "Residential"
    site_manager_id: Optional[str] = None
    columns: list = []              # [{key,label,tag}] tag: plot_id|area|charge|total|reference|ignore
    rate_per_sqft: float = 0        # admin-set sale rate per sq.ft for this project
    created_at: str = Field(default_factory=now)


class ProjectCreate(BaseModel):
    name: str
    location: str = ""
    kind: str = ""
    site_manager_id: Optional[str] = None


class Unit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    unit_id: str = Field(default_factory=lambda: new_id("unit"))
    project_id: str
    plot_number: str
    area: float = 0
    total: float = 0                # Net Payable / grand total for this plot
    data: dict = {}                 # {column_key: value} for every mapped column
    status: Literal["available", "sold"] = "available"
    # sale details (filled by post_sales)
    buyer_name: Optional[str] = None
    buyer_contact: Optional[str] = None
    sale_date: Optional[str] = None
    final_price: float = 0
    booking_amount: float = 0
    sold_by: Optional[str] = None
    sold_at: Optional[str] = None
    created_at: str = Field(default_factory=now)


class PlotUpsert(BaseModel):
    plot_number: str
    data: dict = {}


class ColumnMap(BaseModel):
    key: str
    label: str
    tag: Literal["plot_id", "area", "charge", "total", "reference", "ignore"]


class ScheduleRow(BaseModel):
    due_date: str
    amount: float
    notes: str = ""


class SellUnitRequest(BaseModel):
    buyer_name: str = ""
    buyer_contact: str = ""
    sale_date: str
    final_price: float
    booking_amount: float
    schedule: List[ScheduleRow]


class CancelBookingRequest(BaseModel):
    cancel_date: str
    amount_refunded: float = Field(default=0, ge=0)


class Cancellation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cancellation_id: str = Field(default_factory=lambda: new_id("cancel"))
    unit_id: str
    project_id: str
    plot_number: str
    buyer_name: Optional[str] = None
    amount_paid: float = 0
    amount_refunded: float = 0
    balance_retained: float = 0
    cancel_date: str
    cancelled_by: Optional[str] = None
    cancelled_by_name: Optional[str] = None
    cancelled_at: str = Field(default_factory=now)


class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    payment_id: str = Field(default_factory=lambda: new_id("pay"))
    unit_id: str
    project_id: str
    seq: int                         # 1..N in schedule order
    due_date: str
    amount: float
    notes: str = ""                  # instalment name
    paid_amount: float = 0
    receipts: list = []              # [{amount,date,notes,by,by_name,at}]
    status: Literal["pending", "partial", "received"] = "pending"
    received_date: Optional[str] = None
    received_notes: str = ""
    marked_by: Optional[str] = None
    marked_at: Optional[str] = None


class ReceiptCreate(BaseModel):
    amount: float
    date: Optional[str] = None
    notes: str = ""


class PaymentUpdate(BaseModel):
    status: Literal["pending", "partial", "received"]
    received_date: Optional[str] = None
    received_notes: str = ""


class ProcurementItem(BaseModel):
    name: str
    quantity: float = Field(ge=0)
    unit: str = "pcs"
    est_cost: float = 0
    notes: str = ""


class ProcurementRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    request_id: str = Field(default_factory=lambda: new_id("proc"))
    project_id: str
    subject: str
    items: List[ProcurementItem]
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    notes: str = ""
    status: Literal["pending_admin", "pending_clarification",
                    "approved", "rejected",
                    "po_issued", "paid"] = "pending_admin"
    requested_by: str
    requested_at: str = Field(default_factory=now)
    pi_file: Optional[dict] = None          # Performa Invoice (site manager)
    po_file: Optional[dict] = None          # Purchase Order (accounts)
    po_number: Optional[str] = None
    milestones: list = []                   # [{label,amount,due,status,paid_date,paid_amount,notes}]
    admin_action_by: Optional[str] = None
    admin_action_at: Optional[str] = None
    admin_note: str = ""
    paid_amount: float = 0
    paid_date: Optional[str] = None
    paid_by: Optional[str] = None
    paid_at: Optional[str] = None
    paid_notes: str = ""


class MilestoneItem(BaseModel):
    label: str
    amount: float = 0
    due: str = ""


class MilestonesSet(BaseModel):
    milestones: List[MilestoneItem]


class MilestonePay(BaseModel):
    paid_date: Optional[str] = None
    paid_amount: Optional[float] = None
    notes: str = ""


class ProcurementCreate(BaseModel):
    project_id: str
    subject: str
    items: List[ProcurementItem]
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    notes: str = ""


class AdminAction(BaseModel):
    action: Literal["approve", "reject", "clarify"]
    note: str = ""


class ProcurementPayment(BaseModel):
    po_number: str
    paid_amount: float
    paid_date: str
    notes: str = ""


class InventoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_id: str = Field(default_factory=lambda: new_id("inv"))
    project_id: str
    name: str
    quantity: float = 0
    unit: str = "pcs"
    notes: str = ""
    updated_by: Optional[str] = None
    updated_at: str = Field(default_factory=now)


class InventoryCreate(BaseModel):
    project_id: str
    name: str
    quantity: float = 0
    unit: str = "pcs"
    notes: str = ""


class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notification_id: str = Field(default_factory=lambda: new_id("ntf"))
    user_id: str
    kind: str
    message: str
    link: Optional[str] = None
    is_read: bool = False
    created_at: str = Field(default_factory=now)


# ------------------------------------------------------------------ auth --
async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    doc = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not doc or not doc.get("is_active", True):
        raise HTTPException(401, "User not found or inactive")
    return User(**doc)


def require_roles(*roles: Role):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Role {user.role} not permitted")
        return user
    return _dep


async def notify(user_id: str, kind: str, message: str,
                 link: Optional[str] = None) -> None:
    n = Notification(user_id=user_id, kind=kind, message=message, link=link)
    await db.notifications.insert_one(n.model_dump())


async def notify_role(role: Role, kind: str, message: str,
                      link: Optional[str] = None) -> None:
    async for u in db.users.find({"role": role, "is_active": True},
                                  {"_id": 0, "user_id": 1}):
        await notify(u["user_id"], kind, message, link)


# --------------------------------------------------------------- endpoints -
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}


@api.post("/auth/login")
async def login(payload: LoginRequest):
    doc = await db.users.find_one({"phone": payload.phone}, {"_id": 0})
    if not doc or not doc.get("is_active", True):
        raise HTTPException(401, "Invalid phone or password")
    if not verify_pw(payload.password, doc["password_hash"]):
        raise HTTPException(401, "Invalid phone or password")
    token = make_token(doc["user_id"])
    safe = {k: v for k, v in doc.items() if k != "password_hash"}
    return {"access_token": token, "user": safe}


@api.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return user.model_dump()


@api.post("/auth/change-password")
async def change_password(payload: ChangePasswordRequest,
                          user: User = Depends(get_current_user)):
    doc = await db.users.find_one({"user_id": user.user_id})
    if not verify_pw(payload.current_password, doc["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"password_hash": hash_pw(payload.new_password),
                  "must_reset_password": False}})
    return {"ok": True}


# ----- users (admin only) -------------------------------------------------
@api.get("/users")
async def list_users(user: User = Depends(require_roles("admin"))):
    users = []
    async for u in db.users.find({}, {"_id": 0, "password_hash": 0}):
        users.append(u)
    return users


@api.post("/users")
async def create_user(payload: UserCreate,
                      user: User = Depends(require_roles("admin"))):
    exists = await db.users.find_one({"phone": payload.phone})
    if exists:
        raise HTTPException(400, "A user with this phone already exists")
    if payload.role == "site_manager" and not payload.project_id:
        raise HTTPException(400, "site_manager must have a project_id")
    u = User(**payload.model_dump())
    doc = u.model_dump()
    doc["password_hash"] = hash_pw(payload.phone)  # initial password = phone
    await db.users.insert_one(doc)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@api.patch("/users/{user_id}")
async def update_user(user_id: str, payload: UserCreate,
                      user: User = Depends(require_roles("admin"))):
    updates = payload.model_dump(exclude_unset=True)
    r = await db.users.update_one({"user_id": user_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}


@api.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str,
                                user: User = Depends(require_roles("admin"))):
    doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"password_hash": hash_pw(doc["phone"]),
                  "must_reset_password": True}})
    return {"ok": True, "message": f"Password reset to phone number for {doc['name']}"}


@api.delete("/users/{user_id}")
async def delete_user(user_id: str,
                      user: User = Depends(require_roles("admin"))):
    if user_id == user.user_id:
        raise HTTPException(400, "You cannot delete yourself")
    r = await db.users.delete_one({"user_id": user_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}


# ----- projects (admin only) ----------------------------------------------
@api.get("/projects")
async def list_projects(user: User = Depends(get_current_user)):
    q = {}
    if user.role == "site_manager" and user.project_id:
        q = {"project_id": user.project_id}
    return await db.projects.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/projects")
async def create_project(payload: ProjectCreate,
                          user: User = Depends(require_roles("admin"))):
    p = Project(**payload.model_dump())
    await db.projects.insert_one(p.model_dump())
    if payload.site_manager_id:
        await db.users.update_one(
            {"user_id": payload.site_manager_id, "role": "site_manager"},
            {"$set": {"project_id": p.project_id}})
    return p.model_dump()


@api.patch("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectCreate,
                          user: User = Depends(require_roles("admin"))):
    r = await db.projects.update_one(
        {"project_id": project_id}, {"$set": payload.model_dump(exclude_unset=True)})
    if r.matched_count == 0:
        raise HTTPException(404, "Project not found")
    if payload.site_manager_id:
        await db.users.update_one(
            {"user_id": payload.site_manager_id, "role": "site_manager"},
            {"$set": {"project_id": project_id}})
    return {"ok": True}


class RateUpdate(BaseModel):
    rate_per_sqft: float = Field(default=0, ge=0)


@api.patch("/projects/{project_id}/rate")
async def update_project_rate(project_id: str, payload: RateUpdate,
                               user: User = Depends(require_roles("admin"))):
    r = await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"rate_per_sqft": round(payload.rate_per_sqft, 2)}})
    if r.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return {"ok": True, "rate_per_sqft": round(payload.rate_per_sqft, 2)}


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str,
                          user: User = Depends(require_roles("admin"))):
    r = await db.projects.delete_one({"project_id": project_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Project not found")
    await db.units.delete_many({"project_id": project_id})
    return {"ok": True}


# ----- units --------------------------------------------------------------
def _plot_key(pn: str):
    """Sort key: numeric-aware so 1,2,10 sort naturally."""
    s = str(pn or "")
    import re as _re
    m = _re.match(r"^\s*(\d+(?:\.\d+)?)", s)
    return (0, float(m.group(1)), s) if m else (1, 0.0, s)


@api.get("/units")
async def list_units(project_id: Optional[str] = None,
                      status: Optional[str] = None,
                      user: User = Depends(get_current_user)):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    if status:
        q["status"] = status
    if user.role == "site_manager" and user.project_id:
        q["project_id"] = user.project_id
    rows = await db.units.find(q, {"_id": 0}).to_list(5000)
    rows.sort(key=lambda u: _plot_key(u.get("plot_number")))
    return rows


def _num(v) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else 0.0
    s = str(v).strip()
    for tok in (",", "\u20b9", "Rs.", "Rs", "rs", "INR", "%", " "):
        s = s.replace(tok, "")
    if s in ("", "-", "--", "NA", "N/A", "nil", "Nil"):
        return 0.0
    try:
        f = float(s)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


# Column synonyms for the RERA cost-sheet importer (case/space tolerant).
COL_SYNS = {
    "unit_no": ["unit no", "unit number", "unit", "plot no", "plot number",
                "plot", "farm#", "farm no", "farm number", "farm", "villa no",
                "flat no", "sl no", "s. no", "sr no", "site no"],
    "extent": ["extent", "saleable area", "super built", "built up", "area",
               "sq. ft", "sq ft", "sqft", "sq.ft", "sft", "size"],
    "bsp": ["basic sale price", "basic sale", "basic price", "base price",
            "bsp", "sale price", "unit price", "plot cost", "land cost"],
    "guidance": ["guidance value", "guidance"],
    "east": ["east facing", "east"],
    "hill": ["hill view", "hill", "lake view", "park view", "premium view"],
    "corner": ["corner"],
    "cv_facing": ["cv facing", "cv view", "cauvery"],
    "multi_plc": ["2 or more", "two or more", "more plc", "multiple plc",
                  "2 or more plcs"],
    "infra": ["development charge", "idc", "infrastructure & dev",
              "infrastructure and dev", "infra & dev", "development",
              "infrastructure", "infra"],
    "electricity": ["electricity infrastructure", "electricity", "eb charge",
                    "power infrastructure"],
    "legal": ["legal"],
    "khata": ["khata & registration", "khata", "registration"],
    "club": ["club"],
    "maint": ["advance maintenance", "maintenance", "maint"],
    "ifms": ["ifms", "interest free maintenance"],
    "sinking": ["sinking fund", "sinking"],
    "stamp": ["stamp duty", "stamp"],
    "grand": ["net payable", "total payable", "net amount", "grand total",
              "total amount", "total value", "total cost", "total consideration",
              "all inclusive", "payable", "grand"],
}


def _read_tabular(raw: bytes, fname: str) -> list:
    """Return a list-of-rows from an .xlsx or .csv upload.

    Uses openpyxl read-only streaming and stops after a run of blank rows so
    spreadsheets with tens of thousands of phantom rows/columns (Excel leaves
    these behind after formatting) don't blow up memory or time out.
    """
    if fname.endswith(".csv"):
        return _read_csv(raw)
    try:
        wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
        out, blanks = [], 0
        for r in ws.iter_rows(values_only=True):
            if not any(c not in (None, "") for c in r):
                blanks += 1
                if out and blanks > 25:
                    break
                continue
            blanks = 0
            out.append(list(r))
        wb.close()
        # trim trailing all-empty columns (phantom columns)
        width = max((max((i + 1 for i, v in enumerate(r)
                          if v not in (None, "")), default=0)
                     for r in out), default=0)
        return [r[:width] for r in out]
    except Exception:
        try:
            return _read_csv(raw)
        except Exception:
            raise HTTPException(
                400, "Unsupported or corrupt file. Please upload a .xlsx or .csv.")


def _read_csv(raw: bytes) -> list:
    text = raw.decode("utf-8-sig", errors="replace")
    return [list(r) for r in csv.reader(io.StringIO(text))]


def _detect_header(rows: list):
    """Score the first 30 rows and pick the best header row.

    A valid header must contain a unit/plot column plus at least one more
    recognizable column. Returns (header_idx, idx_map) or (None, None).
    """
    best = None  # (score, i)
    for i, row in enumerate(rows[:30]):
        cells = [str(c or "").strip().lower() for c in row]
        if not any(cells):
            continue
        matched = set()
        for field, syns in COL_SYNS.items():
            if any(c and any(s in c for s in syns) for c in cells):
                matched.add(field)
        if "unit_no" in matched and len(matched) >= 2:
            score = len(matched)
            if best is None or score > best[0]:
                best = (score, i)
    if best is None:
        return None, None
    header_idx = best[1]
    header = [str(c or "").strip().lower() for c in rows[header_idx]]

    def fuzzy(field):
        for s in COL_SYNS[field]:
            for j, h in enumerate(header):
                if s in h:
                    return j
        return None

    return header_idx, {k: fuzzy(k) for k in COL_SYNS}


def _slug(label: str, taken: set) -> str:
    import re as _re
    s = _re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower()).strip("_")
    s = s or "col"
    base, i = s, 2
    while s in taken:
        s = f"{base}_{i}"; i += 1
    taken.add(s)
    return s


def _suggest_tag(label: str, samples: list) -> str:
    l = str(label or "").strip().lower()
    if any(s in l for s in COL_SYNS["unit_no"]):
        return "plot_id"
    if any(s in l for s in ["net payable", "total payable", "grand total",
                            "net amount", "total amount", "total consideration"]):
        return "total"
    if any(s in l for s in COL_SYNS["extent"]):
        return "area"
    if any(s in l for s in ["guidance", "reference", "market value"]):
        return "reference"
    # numeric-looking columns default to charge; text columns to ignore
    numeric = sum(1 for v in samples if _num(v) != 0)
    if "gst" in l or "%" in l:
        return "charge"
    return "charge" if numeric >= max(1, len(samples) // 2) else "ignore"


def _parse_sheet(raw: bytes, fname: str):
    rows = _read_tabular(raw, fname)
    if not rows or not any(any(r) for r in rows):
        raise HTTPException(400, "The uploaded file is empty or unreadable")
    # header row = the row with the most non-empty text cells in first 30
    best_i, best_score = 0, -1
    for i, row in enumerate(rows[:30]):
        cells = [str(c).strip() for c in row if c not in (None, "")]
        texty = sum(1 for c in cells if any(ch.isalpha() for ch in c))
        if texty > best_score:
            best_score, best_i = texty, i
    header = [str(c).strip() for c in rows[best_i]]
    data_rows = [r for r in rows[best_i + 1:] if any(r)]
    return header, data_rows


@api.post("/units/preview")
async def preview_units(project_id: str = Form(...),
                         file: UploadFile = File(...),
                         user: User = Depends(require_roles("admin"))):
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    raw = await file.read()
    header, data_rows = _parse_sheet(raw, (file.filename or "").lower())
    taken: set = set()
    columns = []
    for ci, label in enumerate(header):
        if not str(label).strip():
            continue
        samples = [r[ci] for r in data_rows[:6] if ci < len(r) and r[ci] not in (None, "")]
        columns.append({
            "key": _slug(label, taken),
            "label": str(label).strip(),
            "col_index": ci,
            "tag": _suggest_tag(label, samples),
            "samples": [str(s) for s in samples[:3]],
        })
    return {"columns": columns, "row_count": len(data_rows),
            "filename": file.filename}


@api.post("/units/commit")
async def commit_units(project_id: str = Form(...),
                        file: UploadFile = File(...),
                        mapping: str = Form(...),
                        user: User = Depends(require_roles("admin"))):
    import json as _json
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    cols = _json.loads(mapping)  # [{key,label,col_index,tag}]
    plot_col = next((c for c in cols if c["tag"] == "plot_id"), None)
    if not plot_col:
        raise HTTPException(400, "Please tag exactly one column as 'Plot ID'.")
    area_col = next((c for c in cols if c["tag"] == "area"), None)
    total_col = next((c for c in cols if c["tag"] == "total"), None)
    keep = [c for c in cols if c["tag"] != "ignore"]

    raw = await file.read()
    _, data_rows = _parse_sheet(raw, (file.filename or "").lower())

    def gv(row, c):
        i = c["col_index"]
        return row[i] if i < len(row) else None

    def plot_str(v):
        s = str(v).strip()
        return s[:-2] if s.endswith(".0") else s

    inserted, updated, skipped, errors = 0, 0, [], []
    existing_map = {}
    async for e in db.units.find(
            {"project_id": project_id},
            {"_id": 0, "unit_id": 1, "status": 1, "plot_number": 1}):
        existing_map[e["plot_number"]] = e
    ops = []
    for line, row in enumerate(data_rows, start=2):
        try:
            raw_plot = gv(row, plot_col)
            if raw_plot is None or str(raw_plot).strip() == "":
                continue
            plot = plot_str(raw_plot)
            data = {}
            for c in keep:
                if c["tag"] in ("plot_id",):
                    continue
                val = gv(row, c)
                if c["tag"] in ("charge", "total", "area", "reference"):
                    data[c["key"]] = round(_num(val), 2)
                else:
                    data[c["key"]] = "" if val is None else str(val).strip()
            area = round(_num(gv(row, area_col)), 2) if area_col else 0.0
            total = round(_num(gv(row, total_col)), 2) if total_col else 0.0
            existing = existing_map.get(plot)
            payload = {"project_id": project_id, "plot_number": plot,
                       "area": area, "total": total, "data": data}
            if existing:
                if existing.get("status") == "sold":
                    skipped.append(plot); continue
                ops.append(UpdateOne({"unit_id": existing["unit_id"]},
                                     {"$set": payload}))
                updated += 1
            else:
                ops.append(InsertOne(Unit(**payload).model_dump()))
                inserted += 1
        except Exception as e:
            errors.append({"row": line, "error": str(e)})

    if ops:
        await db.units.bulk_write(ops, ordered=False)

    # persist the column schema on the project
    schema = [{"key": c["key"], "label": c["label"], "tag": c["tag"]} for c in cols]
    await db.projects.update_one({"project_id": project_id},
                                  {"$set": {"columns": schema}})
    return {"inserted": inserted, "updated": updated,
            "skipped_sold": skipped, "errors": errors, "columns": schema}


@api.post("/projects/{project_id}/plots")
async def add_plot(project_id: str, payload: PlotUpsert,
                    user: User = Depends(require_roles("admin"))):
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    plot = str(payload.plot_number).strip()
    if not plot:
        raise HTTPException(400, "Plot number is required")
    if await db.units.find_one({"project_id": project_id, "plot_number": plot}):
        raise HTTPException(400, f"Plot {plot} already exists in this project")
    area, total, data = _clean_plot_data(proj, payload.data)
    u = Unit(project_id=project_id, plot_number=plot, area=area, total=total, data=data)
    await db.units.insert_one(u.model_dump())
    return u.model_dump()


@api.patch("/units/{unit_id}")
async def edit_plot(unit_id: str, payload: PlotUpsert,
                     user: User = Depends(require_roles("admin", "post_sales"))):
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Plot not found")
    proj = await db.projects.find_one({"project_id": unit["project_id"]}, {"_id": 0})
    area, total, data = _clean_plot_data(proj or {}, payload.data)
    await db.units.update_one({"unit_id": unit_id}, {"$set": {
        "plot_number": str(payload.plot_number).strip(),
        "area": area, "total": total, "data": data}})
    return {"ok": True}


def _clean_plot_data(proj: dict, data: dict):
    cols = {c["key"]: c for c in (proj.get("columns") or [])}
    area = total = 0.0
    clean = {}
    for k, v in (data or {}).items():
        c = cols.get(k)
        tag = c["tag"] if c else "charge"
        if tag == "plot_id" or tag == "ignore":
            if tag == "ignore":
                clean[k] = "" if v is None else str(v)
            continue
        if tag in ("charge", "total", "area", "reference"):
            num = round(_num(v), 2)
            clean[k] = num
            if tag == "area":
                area = num
            if tag == "total":
                total = num
        else:
            clean[k] = "" if v is None else str(v)
    return area, total, clean


@api.post("/units/{unit_id}/sell")
async def sell_unit(unit_id: str, payload: SellUnitRequest,
                     user: User = Depends(require_roles("post_sales", "admin"))):
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Unit not found")
    if unit["status"] == "sold":
        raise HTTPException(400, "Unit is already sold")
    if not payload.schedule:
        raise HTTPException(400, "Payment schedule cannot be empty")
    # Update unit
    await db.units.update_one(
        {"unit_id": unit_id},
        {"$set": {"status": "sold",
                  "buyer_name": payload.buyer_name,
                  "buyer_contact": payload.buyer_contact,
                  "sale_date": payload.sale_date,
                  "final_price": payload.final_price,
                  "booking_amount": payload.booking_amount,
                  "sold_by": user.user_id,
                  "sold_at": now()}})
    # Create payment records
    docs = []
    for seq, row in enumerate(payload.schedule, start=1):
        docs.append(Payment(
            unit_id=unit_id, project_id=unit["project_id"],
            seq=seq, due_date=row.due_date, amount=row.amount,
            notes=row.notes).model_dump())
    if docs:
        await db.payments.insert_many(docs)
        for d in docs:
            d.pop("_id", None)
    # Notify admin + accounts (in-app only)
    buyer_txt = f"{payload.buyer_name} · " if payload.buyer_name else ""
    msg = (f"Sale recorded · Plot {unit['plot_number']} · "
           f"{buyer_txt}\u20B9{payload.final_price:,.0f} "
           f"· {len(docs)} installments")
    link = f"/sales"
    await notify_role("admin", "sale_recorded", msg, link)
    await notify_role("accounts", "sale_recorded", msg, link)
    return {"ok": True, "payments": docs}


@api.post("/units/{unit_id}/cancel")
async def cancel_booking(unit_id: str, payload: CancelBookingRequest,
                         user: User = Depends(require_roles("admin"))):
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Unit not found")
    if unit.get("status") != "sold":
        raise HTTPException(400, "Only a booked plot can be cancelled")
    amount_paid = round(await _sum_field(db.payments, {"unit_id": unit_id}, "paid_amount"), 2)
    refunded = round(payload.amount_refunded, 2)
    balance = round(amount_paid - refunded, 2)
    rec = Cancellation(
        unit_id=unit_id, project_id=unit["project_id"], plot_number=unit["plot_number"],
        buyer_name=unit.get("buyer_name"), amount_paid=amount_paid,
        amount_refunded=refunded, balance_retained=balance,
        cancel_date=payload.cancel_date, cancelled_by=user.user_id,
        cancelled_by_name=user.name)
    await db.cancellations.insert_one(rec.model_dump())
    # Remove this booking's payment schedule and free the plot
    await db.payments.delete_many({"unit_id": unit_id})
    await db.units.update_one({"unit_id": unit_id}, {
        "$set": {"status": "available"},
        "$unset": {"buyer_name": "", "buyer_contact": "", "sale_date": "",
                   "final_price": "", "booking_amount": "", "sold_by": "",
                   "sold_at": ""}})
    msg = (f"Booking cancelled · Plot {unit['plot_number']} · paid "
           f"\u20B9{amount_paid:,.0f} · refunded \u20B9{refunded:,.0f} "
           f"· balance \u20B9{balance:,.0f}")
    await notify_role("admin", "booking_cancelled", msg, "/sales")
    await notify_role("accounts", "booking_cancelled", msg, "/sales")
    return {"ok": True, "cancellation": rec.model_dump()}


@api.get("/cancellations")
async def list_cancellations(project_id: Optional[str] = None,
                             user: User = Depends(require_roles("admin", "accounts"))):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    return await db.cancellations.find(q, {"_id": 0}).sort("cancelled_at", -1).to_list(1000)


# ----- payments (accounts) ------------------------------------------------
@api.get("/payments")
async def list_payments(project_id: Optional[str] = None,
                         status: Optional[str] = None,
                         unit_id: Optional[str] = None,
                         user: User = Depends(get_current_user)):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    if status:
        q["status"] = status
    if unit_id:
        q["unit_id"] = unit_id
    return await db.payments.find(q, {"_id": 0}).sort("due_date", 1).to_list(2000)


@api.patch("/payments/{payment_id}")
async def update_payment(payment_id: str, payload: PaymentUpdate,
                          user: User = Depends(require_roles("accounts", "admin"))):
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    updates = {
        "status": payload.status,
        "received_date": payload.received_date,
        "received_notes": payload.received_notes,
        "marked_by": user.user_id,
        "marked_at": now(),
    }
    if payload.status == "received":
        updates["paid_amount"] = round(pay["amount"], 2)
    elif payload.status == "pending":
        updates["paid_amount"] = 0
        updates["receipts"] = []
    await db.payments.update_one({"payment_id": payment_id}, {"$set": updates})
    unit = await db.units.find_one({"unit_id": pay["unit_id"]}, {"_id": 0})
    if payload.status == "received":
        await notify_role(
            "admin", "payment_received",
            f"Payment received · Plot {unit.get('plot_number')} · "
            f"\u20B9{pay['amount']:,.2f}", "/sales")
    return {"ok": True}


@api.post("/payments/{payment_id}/receipt")
async def add_receipt(payment_id: str, payload: ReceiptCreate,
                       user: User = Depends(require_roles("accounts", "admin"))):
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    amt = round(_num(payload.amount), 2)
    if amt <= 0:
        raise HTTPException(400, "Receipt amount must be greater than zero")
    new_paid = round((pay.get("paid_amount") or 0) + amt, 2)
    receipt = {
        "amount": amt,
        "date": payload.date or datetime.now(timezone.utc).date().isoformat(),
        "notes": payload.notes or "",
        "by": user.user_id, "by_name": user.name, "at": now(),
    }
    status = "received" if new_paid >= round(pay["amount"], 2) - 0.01 else "partial"
    await db.payments.update_one({"payment_id": payment_id}, {
        "$set": {"paid_amount": new_paid, "status": status,
                 "received_date": receipt["date"], "marked_by": user.user_id,
                 "marked_at": now()},
        "$push": {"receipts": receipt}})
    unit = await db.units.find_one({"unit_id": pay["unit_id"]}, {"_id": 0})
    verb = "fully received" if status == "received" else "part-paid"
    await notify_role(
        "admin", "payment_received",
        f"Plot {unit.get('plot_number')} · {pay.get('notes') or 'instalment'} "
        f"{verb} · \u20B9{amt:,.2f}", "/sales")
    return {"ok": True, "paid_amount": new_paid, "status": status}


# ----- procurement (site_manager -> admin -> accounts) -------------------
@api.get("/accounts/overview")
async def accounts_overview(user: User = Depends(require_roles("accounts", "admin"))):
    payments = await db.payments.find({}, {"_id": 0}).to_list(20000)
    units = await db.units.find(
        {"status": "sold"},
        {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1, "project_id": 1}).to_list(5000)
    umap = {u["unit_id"]: u for u in units}
    projects = await db.projects.find({}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)
    pname = {p["project_id"]: p["name"] for p in projects}

    by_unit: dict = {}
    for p in payments:
        by_unit.setdefault(p["unit_id"], []).append(p)

    rows_by_proj: dict = {}
    for uid, pays in by_unit.items():
        u = umap.get(uid, {})
        proj = u.get("project_id") or pays[0].get("project_id")
        total = round(sum(x["amount"] for x in pays), 2)
        paid = round(sum((x.get("paid_amount") or 0) for x in pays), 2)
        due_pending = [x["due_date"] for x in pays if x["status"] != "received"]
        rows_by_proj.setdefault(proj, []).append({
            "unit_id": uid, "plot_number": u.get("plot_number", "?"),
            "buyer_name": u.get("buyer_name"), "project_id": proj,
            "project_name": pname.get(proj, ""),
            "total": total, "paid": paid, "pending": round(total - paid, 2),
            "installments": len(pays),
            "next_due": sorted(due_pending)[0] if due_pending else None,
        })

    plots_projects, ptot = [], {"total": 0.0, "paid": 0.0}
    for proj, rows in rows_by_proj.items():
        rows.sort(key=lambda r: _plot_key(r["plot_number"]))
        pt = round(sum(r["total"] for r in rows), 2)
        pp = round(sum(r["paid"] for r in rows), 2)
        plots_projects.append({
            "project_id": proj, "name": pname.get(proj, ""), "plot_count": len(rows),
            "total": pt, "paid": pp, "pending": round(pt - pp, 2), "plots": rows})
        ptot["total"] += pt; ptot["paid"] += pp
    plots_projects.sort(key=lambda x: x["name"])
    plots_totals = {"total": round(ptot["total"], 2), "paid": round(ptot["paid"], 2),
                    "pending": round(ptot["total"] - ptot["paid"], 2)}

    # Site head = procurement bills (PO issued / paid, with milestones)
    procs = await db.procurement.find(
        {"status": {"$in": ["approved", "po_issued", "paid"]}}, {"_id": 0}).to_list(500)
    site_rows, s_pending, s_paid = [], 0.0, 0.0
    for r in procs:
        ms = r.get("milestones") or []
        if ms:
            est = round(sum(m.get("amount", 0) for m in ms), 2)
            paid = round(sum((m.get("paid_amount", 0) or 0) for m in ms if m.get("status") == "paid"), 2)
        else:
            est = round(sum((i.get("est_cost", 0) * i.get("quantity", 0))
                            for i in r.get("items", [])), 2)
            paid = round(r.get("paid_amount", 0) or 0, 2)
        pend = max(0.0, round(est - paid, 2))
        site_rows.append({
            "request_id": r["request_id"], "subject": r["subject"],
            "project_name": pname.get(r["project_id"], ""), "status": r["status"],
            "est_total": est, "paid": paid, "pending": pend,
            "po_number": r.get("po_number"),
            "milestones": ms})
        s_pending += pend; s_paid += paid

    return {
        "plots": {"projects": plots_projects, "totals": plots_totals},
        "site": {"rows": site_rows, "pending_total": round(s_pending, 2),
                 "paid_total": round(s_paid, 2)},
    }


@api.get("/procurement")
async def list_procurement(user: User = Depends(get_current_user)):
    q: dict = {}
    if user.role == "site_manager" and user.project_id:
        q["project_id"] = user.project_id
    return await db.procurement.find(q, {"_id": 0}).sort("requested_at", -1).to_list(500)


@api.post("/procurement")
async def create_procurement(
        project_id: str = Form(...),
        subject: str = Form(...),
        items: str = Form(...),
        priority: str = Form("medium"),
        notes: str = Form(""),
        file: Optional[UploadFile] = File(None),
        user: User = Depends(require_roles("site_manager", "admin"))):
    if user.role == "site_manager" and user.project_id != project_id:
        raise HTTPException(403, "Project not in your scope")
    try:
        item_list = json.loads(items)
    except Exception:
        raise HTTPException(400, "Invalid items payload")
    if not item_list:
        raise HTTPException(400, "At least one item is required")
    pi_ref = await save_upload(file, "procurement/pi", user.user_id) if file else None
    r = ProcurementRequest(
        project_id=project_id, subject=subject,
        items=[ProcurementItem(**i) for i in item_list],
        priority=priority, notes=notes, requested_by=user.user_id, pi_file=pi_ref)
    await db.procurement.insert_one(r.model_dump())
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0}) or {}
    await notify_role("admin", "procurement_new",
                      f"Procurement request · {subject} · {proj.get('name','')} · "
                      f"Priority: {priority}", "/procurement")
    return r.model_dump()


@api.post("/procurement/{request_id}/po")
async def issue_po(request_id: str,
                    po_number: str = Form(...),
                    file: Optional[UploadFile] = File(None),
                    user: User = Depends(require_roles("accounts", "admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] not in ("approved", "po_issued"):
        raise HTTPException(400, "Only approved requests can get a PO")
    po_ref = await save_upload(file, "procurement/po", user.user_id) if file else doc.get("po_file")
    await db.procurement.update_one({"request_id": request_id}, {"$set": {
        "status": "po_issued", "po_number": po_number, "po_file": po_ref}})
    await notify(doc["requested_by"], "procurement_po",
                 f"PO issued for '{doc['subject']}' · PO {po_number}", "/procurement")
    await notify_role("admin", "procurement_po",
                      f"PO {po_number} issued · {doc['subject']}", "/procurement")
    return {"ok": True, "status": "po_issued"}


@api.post("/procurement/{request_id}/milestones")
async def set_milestones(request_id: str, payload: MilestonesSet,
                          user: User = Depends(require_roles("accounts", "admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] not in ("po_issued", "paid"):
        raise HTTPException(400, "Issue a PO before setting the payment structure")
    existing = doc.get("milestones") or []
    milestones = []
    for i, m in enumerate(payload.milestones):
        prev = existing[i] if i < len(existing) else {}
        milestones.append({
            "label": m.label, "amount": round(_num(m.amount), 2), "due": m.due,
            "status": prev.get("status", "pending"),
            "paid_date": prev.get("paid_date"), "paid_amount": prev.get("paid_amount", 0),
            "notes": prev.get("notes", ""),
        })
    await db.procurement.update_one({"request_id": request_id},
                                     {"$set": {"milestones": milestones}})
    await notify_role("admin", "procurement_milestones",
                      f"Payment structure set for '{doc['subject']}' "
                      f"({len(milestones)} milestone(s))", "/procurement")
    return {"ok": True, "milestones": milestones}


@api.post("/procurement/{request_id}/milestones/{idx}/pay")
async def pay_milestone(request_id: str, idx: int, payload: MilestonePay,
                         user: User = Depends(require_roles("accounts", "admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    ms = doc.get("milestones") or []
    if idx < 0 or idx >= len(ms):
        raise HTTPException(404, "Milestone not found")
    ms[idx]["status"] = "paid"
    ms[idx]["paid_date"] = payload.paid_date or datetime.now(timezone.utc).date().isoformat()
    ms[idx]["paid_amount"] = round(_num(payload.paid_amount if payload.paid_amount is not None else ms[idx]["amount"]), 2)
    ms[idx]["notes"] = payload.notes or ms[idx].get("notes", "")
    all_paid = all(m["status"] == "paid" for m in ms)
    total_paid = round(sum(m.get("paid_amount", 0) for m in ms), 2)
    updates = {"milestones": ms, "paid_amount": total_paid}
    if all_paid:
        updates["status"] = "paid"; updates["paid_by"] = user.user_id
        updates["paid_at"] = now(); updates["paid_date"] = ms[idx]["paid_date"]
    await db.procurement.update_one({"request_id": request_id}, {"$set": updates})
    await notify_role("admin", "procurement_milestone_paid",
                      f"Milestone '{ms[idx]['label']}' paid · {doc['subject']} · "
                      f"\u20B9{ms[idx]['paid_amount']:,.2f}", "/procurement")
    return {"ok": True, "all_paid": all_paid, "paid_amount": total_paid}


@api.get("/files/{file_id}/download")
async def download_file(file_id: str, authorization: str = Header(None),
                         auth: str = Query(None),
                         token: Optional[str] = Query(None)):
    tok = None
    if authorization and authorization.startswith("Bearer "):
        tok = authorization[7:]
    tok = tok or auth or token
    if not tok:
        raise HTTPException(401, "Missing token")
    try:
        jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(401, "Invalid token")
    rec = await db.files.find_one({"file_id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    data, ctype = get_object(rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type", ctype),
                    headers={"Content-Disposition":
                             f'inline; filename="{rec.get("original_filename", "file")}"'})


@api.post("/procurement/{request_id}/action")
async def admin_action_procurement(request_id: str, payload: AdminAction,
                                    user: User = Depends(require_roles("admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] not in ("pending_admin", "pending_clarification"):
        raise HTTPException(400, f"Cannot act on request in status {doc['status']}")
    if payload.action == "approve":
        new_status = "approved"
    elif payload.action == "reject":
        new_status = "rejected"
    else:
        new_status = "pending_clarification"
    await db.procurement.update_one(
        {"request_id": request_id},
        {"$set": {"status": new_status,
                  "admin_action_by": user.user_id,
                  "admin_action_at": now(),
                  "admin_note": payload.note}})
    msg = f"Procurement '{doc['subject']}' — {payload.action}"
    if payload.note:
        msg += f" · {payload.note}"
    await notify(doc["requested_by"], f"procurement_{payload.action}",
                 msg, "/procurement")
    if new_status == "approved":
        await notify_role("accounts", "procurement_approved",
                          f"Approved procurement ready for PO/payment · "
                          f"{doc['subject']}", "/procurement")
    return {"ok": True, "status": new_status}


# ----- inventory (site_manager) ------------------------------------------
@api.get("/inventory")
async def list_inventory(project_id: Optional[str] = None,
                          user: User = Depends(get_current_user)):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    if user.role == "site_manager" and user.project_id:
        q["project_id"] = user.project_id
    return await db.inventory.find(q, {"_id": 0}).sort("name", 1).to_list(500)


@api.post("/inventory")
async def create_inventory(payload: InventoryCreate,
                            user: User = Depends(require_roles("site_manager", "admin"))):
    if user.role == "site_manager" and user.project_id != payload.project_id:
        raise HTTPException(403, "Project not in your scope")
    item = InventoryItem(**payload.model_dump(),
                          updated_by=user.user_id, updated_at=now())
    await db.inventory.insert_one(item.model_dump())
    return item.model_dump()


@api.patch("/inventory/{item_id}")
async def update_inventory(item_id: str, payload: InventoryUpdate,
                            user: User = Depends(require_roles("site_manager", "admin"))):
    doc = await db.inventory.find_one({"item_id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Item not found")
    if user.role == "site_manager" and user.project_id != doc["project_id"]:
        raise HTTPException(403, "Project not in your scope")
    updates = payload.model_dump(exclude_unset=True)
    updates["updated_by"] = user.user_id
    updates["updated_at"] = now()
    await db.inventory.update_one({"item_id": item_id}, {"$set": updates})
    return {"ok": True}


@api.delete("/inventory/{item_id}")
async def delete_inventory(item_id: str,
                            user: User = Depends(require_roles("site_manager", "admin"))):
    doc = await db.inventory.find_one({"item_id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Item not found")
    if user.role == "site_manager" and user.project_id != doc["project_id"]:
        raise HTTPException(403, "Project not in your scope")
    await db.inventory.delete_one({"item_id": item_id})
    return {"ok": True}


# ----- notifications -----------------------------------------------------
@api.get("/notifications")
async def list_notifications(user: User = Depends(get_current_user)):
    return await db.notifications.find(
        {"user_id": user.user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)


@api.post("/notifications/{nid}/read")
async def mark_notification_read(nid: str,
                                  user: User = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": nid, "user_id": user.user_id},
        {"$set": {"is_read": True}})
    return {"ok": True}


@api.post("/notifications/read-all")
async def mark_all_read(user: User = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user.user_id, "is_read": False},
        {"$set": {"is_read": True}})
    return {"ok": True}


# ----- dashboard ---------------------------------------------------------
async def _sum_amount(coll, match: dict) -> float:
    cur = coll.aggregate([{"$match": match},
                          {"$group": {"_id": None, "s": {"$sum": "$amount"}}}])
    rows = await cur.to_list(1)
    return float(rows[0]["s"]) if rows else 0.0


async def _sum_field(coll, match: dict, field: str) -> float:
    cur = coll.aggregate([{"$match": match},
                          {"$group": {"_id": None, "s": {"$sum": f"${field}"}}}])
    rows = await cur.to_list(1)
    return float(rows[0]["s"]) if rows else 0.0


async def _projects_overview():
    projects = await db.projects.find({}, {"_id": 0}).sort("created_at", 1).to_list(50)
    out = []
    con = {"projects": len(projects), "total_units": 0, "available": 0, "sold": 0,
           "booked_value": 0.0, "received_total": 0.0, "pending_total": 0.0}
    for p in projects:
        pid = p["project_id"]
        units = await db.units.find(
            {"project_id": pid},
            {"_id": 0, "status": 1, "total": 1, "data": 1, "final_price": 1}).to_list(5000)
        sold = [u for u in units if u.get("status") == "sold"]
        booked = round(sum((u.get("total") or u.get("final_price") or 0) for u in sold), 2)
        received = round(await _sum_field(db.payments, {"project_id": pid}, "paid_amount"), 2)
        retained = round(await _sum_field(db.cancellations, {"project_id": pid}, "balance_retained"), 2)
        received = round(received + retained, 2)
        pending = round(max(0.0, booked - received), 2)
        pivots = []
        for c in (p.get("columns") or []):
            if c["tag"] not in ("charge", "total", "reference"):
                continue
            k = c["key"]
            pivots.append({
                "key": k, "label": c["label"], "tag": c["tag"],
                "sum_all": round(sum(_num(u.get("data", {}).get(k)) for u in units), 2),
                "sum_sold": round(sum(_num(u.get("data", {}).get(k)) for u in sold), 2),
            })
        out.append({
            "project_id": pid, "name": p["name"], "kind": p.get("kind", ""),
            "columns": p.get("columns", []),
            "total_units": len(units), "available": len(units) - len(sold), "sold": len(sold),
            "booked_value": booked, "received_total": received, "pending_total": pending,
            "pivots": pivots,
        })
        con["total_units"] += len(units); con["available"] += len(units) - len(sold)
        con["sold"] += len(sold); con["booked_value"] += booked
        con["received_total"] += received; con["pending_total"] += pending
    for k in ("booked_value", "received_total", "pending_total"):
        con[k] = round(con[k], 2)
    return out, con


@api.get("/dashboard")
async def dashboard(user: User = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date().isoformat()
    proj_q: dict = {}
    if user.role == "site_manager" and user.project_id:
        proj_q = {"project_id": user.project_id}

    # ---- shared counts (kept for backward compatibility) ----
    projects = await db.projects.count_documents(proj_q)
    units_available = await db.units.count_documents({**proj_q, "status": "available"})
    units_sold = await db.units.count_documents({**proj_q, "status": "sold"})
    payments_pending = await db.payments.count_documents({**proj_q, "status": "pending"})
    procurement_pending = await db.procurement.count_documents(
        {**proj_q, "status": {"$in": ["pending_admin", "pending_clarification"]}})

    base = {
        "role": user.role,
        "projects": projects,
        "units_available": units_available,
        "units_sold": units_sold,
        "payments_pending": payments_pending,
        "procurement_pending": procurement_pending,
    }

    # ================= ADMIN =================
    if user.role == "admin":
        by_project, consolidated = await _projects_overview()
        sales_booked = await _sum_field(db.units, {"status": "sold"}, "final_price")
        pending_amt = await _sum_amount(db.payments, {"status": "pending"})
        received_amt = await _sum_amount(db.payments, {"status": "received"})
        team = await db.users.count_documents({})
        approvals = await db.procurement.find(
            {"status": {"$in": ["pending_admin", "pending_clarification"]}},
            {"_id": 0}).sort("requested_at", -1).limit(6).to_list(6)
        recent_sales = await db.units.find(
            {"status": "sold"}, {"_id": 0}).sort("sold_at", -1).limit(6).to_list(6)
        proc_paid = await db.procurement.count_documents({"status": "paid"})
        site_procs = await db.procurement.find(
            {"status": {"$in": ["po_issued", "paid"]}}, {"_id": 0}).to_list(500)
        site_pending = site_paid = 0.0
        site_milestones = []
        for r in site_procs:
            ms = r.get("milestones") or []
            est = round(sum(m.get("amount", 0) for m in ms), 2) if ms else round(r.get("paid_amount", 0), 2)
            paid = round(sum((m.get("paid_amount", 0) or 0) for m in ms if m.get("status") == "paid"), 2)
            site_pending += max(0.0, est - paid); site_paid += paid
            for m in ms:
                site_milestones.append({"subject": r["subject"], "po_number": r.get("po_number"),
                                        "label": m.get("label"), "amount": m.get("amount"),
                                        "due": m.get("due"), "status": m.get("status")})
        base.update({
            "sales_booked": sales_booked,
            "payments_pending_amount": pending_amt,
            "payments_received_amount": received_amt,
            "team_members": team,
            "procurement_approvals": approvals,
            "procurement_paid": proc_paid,
            "site_bills": {"pending": round(site_pending, 2), "paid": round(site_paid, 2),
                           "count": len(site_procs),
                           "milestones": sorted(site_milestones, key=lambda x: (x["status"] == "paid", x.get("due") or ""))[:8]},
            "recent_sales": recent_sales,
            "by_project": by_project,
            "consolidated": consolidated,
        })
        return base

    # ================= POST-SALES =================
    if user.role == "post_sales":
        by_project, consolidated = await _projects_overview()
        sales_booked = await _sum_field(db.units, {"status": "sold"}, "final_price")
        my_sales = await db.units.count_documents({"status": "sold", "sold_by": user.user_id})
        my_value = await _sum_field(db.units, {"status": "sold", "sold_by": user.user_id}, "final_price")
        recent_sales = await db.units.find(
            {"status": "sold"}, {"_id": 0}).sort("sold_at", -1).limit(8).to_list(8)
        base.update({
            "sales_booked": sales_booked,
            "my_sales_count": my_sales,
            "my_sales_value": my_value,
            "recent_sales": recent_sales,
            "by_project": by_project,
            "consolidated": consolidated,
        })
        return base

    # ================= ACCOUNTS =================
    if user.role == "accounts":
        by_project, consolidated = await _projects_overview()
        pending_amt = await _sum_amount(db.payments, {"status": "pending"})
        overdue_q = {"status": "pending", "due_date": {"$lt": today}}
        overdue_count = await db.payments.count_documents(overdue_q)
        overdue_amt = await _sum_amount(db.payments, overdue_q)
        received_count = await db.payments.count_documents({"status": "received"})
        received_amt = await _sum_amount(db.payments, {"status": "received"})
        awaiting_po = await db.procurement.find(
            {"status": "approved"}, {"_id": 0}).sort("admin_action_at", -1).limit(8).to_list(8)
        watchlist = await db.payments.find(
            {"status": "pending"}, {"_id": 0}).sort("due_date", 1).limit(10).to_list(10)
        # enrich watchlist with plot/buyer
        unit_ids = list({p["unit_id"] for p in watchlist})
        units = await db.units.find({"unit_id": {"$in": unit_ids}},
                                    {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1}).to_list(200)
        umap = {u["unit_id"]: u for u in units}
        for p in watchlist:
            u = umap.get(p["unit_id"], {})
            p["plot_number"] = u.get("plot_number")
            p["buyer_name"] = u.get("buyer_name")
        base.update({
            "payments_pending_amount": pending_amt,
            "payments_overdue_count": overdue_count,
            "payments_overdue_amount": overdue_amt,
            "payments_received_count": received_count,
            "payments_received_amount": received_amt,
            "procurement_awaiting_po": awaiting_po,
            "watchlist": watchlist,
            "by_project": by_project,
            "consolidated": consolidated,
        })
        return base

    # ================= SITE MANAGER =================
    if user.role == "site_manager":
        inv_q = proj_q
        inventory_count = await db.inventory.count_documents(inv_q)
        low_stock = await db.inventory.find(
            {**inv_q, "quantity": {"$lte": 10}}, {"_id": 0}).sort("quantity", 1).limit(8).to_list(8)
        my_proc_q = {}
        if user.project_id:
            my_proc_q = {"project_id": user.project_id}
        proc_by_status = {}
        for st in ["pending_admin", "pending_clarification", "approved", "paid", "rejected"]:
            proc_by_status[st] = await db.procurement.count_documents({**my_proc_q, "status": st})
        recent_proc = await db.procurement.find(
            my_proc_q, {"_id": 0}).sort("requested_at", -1).limit(8).to_list(8)
        base.update({
            "inventory_count": inventory_count,
            "low_stock": low_stock,
            "procurement_by_status": proc_by_status,
            "recent_procurement": recent_proc,
        })
        return base

    return base


# ----- global search -----------------------------------------------------
@api.get("/search")
async def global_search(q: str = "", user: User = Depends(get_current_user)):
    q = (q or "").strip()
    if len(q) < 2:
        return {"results": []}
    rx = {"$regex": q, "$options": "i"}
    results: list[dict] = []
    is_sm = user.role == "site_manager"
    scope = {"project_id": user.project_id} if (is_sm and user.project_id) else {}

    # Units (plots) — admin, post_sales, accounts see all; site_manager scoped
    if user.role in ("admin", "post_sales", "accounts", "site_manager"):
        uq = {**scope, "$or": [{"plot_number": rx}, {"buyer_name": rx}, {"buyer_contact": rx}]}
        for u in await db.units.find(uq, {"_id": 0}).limit(6).to_list(6):
            results.append({
                "type": "unit", "id": u["unit_id"],
                "label": f"Plot {u.get('plot_number')}",
                "sublabel": (u.get("buyer_name") and f"{u['status'].title()} · {u['buyer_name']}") or u.get("status", "").title(),
                "link": "/units",
            })

    # Projects — admin, post_sales, accounts
    if user.role in ("admin", "post_sales", "accounts"):
        for p in await db.projects.find({"$or": [{"name": rx}, {"location": rx}]}, {"_id": 0}).limit(5).to_list(5):
            results.append({
                "type": "project", "id": p["project_id"], "label": p.get("name"),
                "sublabel": p.get("location") or "Project",
                "link": "/projects" if user.role == "admin" else "/units",
            })

    # Procurement — admin, accounts (all), site_manager (own project)
    if user.role in ("admin", "accounts", "site_manager"):
        pq = {**scope, "subject": rx}
        for r in await db.procurement.find(pq, {"_id": 0}).limit(6).to_list(6):
            results.append({
                "type": "procurement", "id": r["request_id"], "label": r.get("subject"),
                "sublabel": f"{r.get('status', '').replace('_', ' ').title()} · {r.get('priority', '')}",
                "link": "/procurement",
            })

    # Inventory — admin (all), site_manager (own)
    if user.role in ("admin", "site_manager"):
        for it in await db.inventory.find({**scope, "name": rx}, {"_id": 0}).limit(6).to_list(6):
            results.append({
                "type": "inventory", "id": it["item_id"], "label": it.get("name"),
                "sublabel": f"{it.get('quantity')} {it.get('unit')} in stock",
                "link": "/inventory",
            })

    # Team — admin only
    if user.role == "admin":
        for m in await db.users.find({"$or": [{"name": rx}, {"phone": rx}]}, {"_id": 0}).limit(5).to_list(5):
            results.append({
                "type": "user", "id": m["user_id"], "label": m.get("name"),
                "sublabel": f"{ROLE_LABELS_PY.get(m.get('role'), m.get('role'))} · {m.get('phone')}",
                "link": "/users",
            })

    return {"results": results[:20]}


ROLE_LABELS_PY = {
    "admin": "Admin", "accounts": "Accounts",
    "post_sales": "Post-Sales Rep", "site_manager": "Site Manager",
}



# ----- startup ------------------------------------------------------------
app.include_router(api)


def _has_nonfinite(v) -> bool:
    if isinstance(v, float):
        return not math.isfinite(v)
    if isinstance(v, dict):
        return any(_has_nonfinite(x) for x in v.values())
    if isinstance(v, list):
        return any(_has_nonfinite(x) for x in v)
    return False


async def _scrub_nonfinite_data():
    """Replace any NaN/Infinity numbers already stored in the DB with 0 so
    aggregations and JSON serialization can never break on bad spreadsheet data.
    Runs on startup; cheap for these collection sizes."""
    fixed = 0
    for coll in (db.units, db.payments, db.cancellations):
        async for doc in coll.find({}):
            if _has_nonfinite(doc):
                clean = _sanitize_nonfinite({k: v for k, v in doc.items() if k != "_id"})
                clean = {k: (0.0 if v is None and isinstance(doc.get(k), float) else v)
                         for k, v in clean.items()}
                await coll.update_one({"_id": doc["_id"]}, {"$set": clean})
                fixed += 1
    if fixed:
        log.info("Scrubbed non-finite numbers from %d document(s)", fixed)


@app.on_event("startup")
async def startup():
    await db.users.create_index("phone", unique=True)
    await db.units.create_index("unit_id")
    await db.units.create_index([("project_id", 1), ("plot_number", 1)])
    await _scrub_nonfinite_data()
    try:
        init_storage()
        log.info("Object storage initialised")
    except Exception as e:
        log.warning("Object storage init failed (will retry on demand): %s", e)
    # Provision the initial admin if the users collection is empty
    n = await db.users.count_documents({})
    if n == 0:
        admin = User(
            name="Admin", phone=ADMIN_PHONE, email=ADMIN_EMAIL, role="admin",
            must_reset_password=True,
        )
        doc = admin.model_dump()
        doc["password_hash"] = hash_pw(ADMIN_PHONE)
        await db.users.insert_one(doc)
        log.info(
            "Provisioned initial admin: phone=%s (initial password = phone)",
            ADMIN_PHONE)


@app.on_event("shutdown")
async def shutdown():
    client.close()
