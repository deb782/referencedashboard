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
    Body, Depends, FastAPI, File, Form, HTTPException, Header, Query, UploadFile,
)
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
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
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="uploads")

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


class StorageError(Exception):
    def __init__(self, status: int, body: str = ""):
        self.status = status
        self.body = body
        super().__init__(f"storage {status}: {body[:200]}")


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=(5, 8))
    if resp.status_code != 200:
        raise StorageError(resp.status_code, f"init: {resp.text or ''}")
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
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=(5, 15))
    # 404 can mean a dead session key -> mint a fresh key once and retry.
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=(5, 15))
    if resp.status_code != 200:
        raise StorageError(resp.status_code, resp.text or "")
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def save_upload(file: UploadFile, folder: str, user_id: str) -> dict:
    ext = (file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "bin")
    file_id = new_id("file")
    data = await file.read()
    ctype = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    # Store the bytes in MongoDB via GridFS (durable, replica-safe, works in prod).
    gid = await fs_bucket.upload_from_stream(
        f"{file_id}.{ext}", data,
        metadata={"file_id": file_id, "content_type": ctype, "folder": folder,
                  "uploaded_by": user_id, "original_filename": file.filename})
    ref = {
        "file_id": file_id, "gridfs_id": str(gid), "storage_backend": "gridfs",
        "original_filename": file.filename, "content_type": ctype,
        "size": len(data), "uploaded_by": user_id,
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
Role = Literal["admin", "accounts", "post_sales", "site_manager", "management"]

# sections a management user can be granted view/approve access to (admin-configurable)
MGMT_SECTIONS = ["projects", "users", "units", "sales", "inventory", "procurement"]


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str = Field(default_factory=lambda: new_id("usr"))
    name: str
    phone: str
    email: Optional[EmailStr] = None
    role: Role
    project_id: Optional[str] = None   # site_managers & management are scoped to one project
    permissions: list = []             # sections a management user can access
    is_active: bool = True
    must_reset_password: bool = True
    created_at: str = Field(default_factory=now)


class UserCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    role: Role
    project_id: Optional[str] = None
    permissions: Optional[list] = None


class AccessUpdate(BaseModel):
    permissions: List[str] = []
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
    vault: Optional[dict] = None          # {variant_id,label,construction,gst,total}
    vault_schedule: List[ScheduleRow] = []


class ScheduleEditRow(BaseModel):
    payment_id: Optional[str] = None
    due_date: str
    amount: float
    notes: str = ""


class ScheduleEdit(BaseModel):
    installments: List[ScheduleEditRow]
    stream: Literal["land", "vault"] = "land"


class AutoFitRequest(BaseModel):
    payment_id: str


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
    stream: Literal["land", "vault"] = "land"   # revenue stream: base plot vs The Vault add-on
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
    mode: str = ""
    head: str = ""
    allocations: list = []                       # [{key,label,amount}]
    expected_remaining_date: Optional[str] = None


class VerifyDecision(BaseModel):
    decision: Literal["yes", "no"]
    reason: str = ""
    notes: str = ""


class AllocationEdit(BaseModel):
    allocations: list = []                       # [{key,label,amount}]


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
    status: Literal["pending_management", "management_clarification",
                    "pending_admin", "pending_clarification",
                    "approved", "rejected",
                    "po_issued", "paid", "cancelled"] = "pending_admin"
    requested_by: str
    requested_at: str = Field(default_factory=now)
    pi_file: Optional[dict] = None          # Performa Invoice (site manager)
    pi_history: List[dict] = []             # previously rejected/replaced PIs
    po_file: Optional[dict] = None          # Purchase Order (accounts)
    tax_invoice_file: Optional[dict] = None # Tax Invoice (site manager/accounts, PO stage)
    pi_amount: float = 0                    # total PI value (site manager)
    po_number: Optional[str] = None
    accounts_note: str = ""                 # Accounts comment back to site manager
    milestones: list = []                   # [{label,amount,due,status,paid_date,paid_amount,notes}]
    mgmt_action_by: Optional[str] = None
    mgmt_action_at: Optional[str] = None
    mgmt_note: str = ""
    mgmt_decision: Optional[str] = None
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


class MgmtAction(BaseModel):
    action: Literal["approve", "reject", "clarify"]
    note: str = ""


class ProcCancel(BaseModel):
    reason: str = ""


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


def require_section(section: str, *roles: Role):
    """Allow the given roles OR a management user that has `section` granted."""
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role == "management":
            if section not in (user.permissions or []):
                raise HTTPException(403, "Section not permitted for this account")
            return user
        if user.role not in roles:
            raise HTTPException(403, f"Role {user.role} not permitted")
        return user
    return _dep


def require_report_access():
    """Payment report: everyone except site_manager. Management needs sales OR units."""
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role == "management":
            perms = user.permissions or []
            if "sales" in perms or "units" in perms:
                return user
            raise HTTPException(403, "Section not permitted for this account")
        if user.role not in ("admin", "accounts", "post_sales"):
            raise HTTPException(403, f"Role {user.role} not permitted")
        return user
    return _dep


def _mgmt_gate(user: User, section: str):
    if user.role == "management" and section not in (user.permissions or []):
        raise HTTPException(403, "Section not permitted for this account")


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
async def list_users(user: User = Depends(require_section("users", "admin"))):
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
    if payload.role in ("site_manager", "management") and not payload.project_id:
        raise HTTPException(400, f"{payload.role} must have a project_id")
    data = payload.model_dump()
    if data.get("permissions") is None:
        data.pop("permissions", None)
    u = User(**data)
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


@api.patch("/users/{user_id}/access")
async def update_user_access(user_id: str, payload: AccessUpdate,
                             user: User = Depends(require_roles("admin"))):
    doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    bad = [s for s in payload.permissions if s not in MGMT_SECTIONS]
    if bad:
        raise HTTPException(400, f"Unknown sections: {', '.join(bad)}")
    updates: dict = {"permissions": payload.permissions}
    if payload.project_id is not None:
        updates["project_id"] = payload.project_id
    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    return {"ok": True, "permissions": payload.permissions}


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
    if user.role in ("site_manager", "management") and user.project_id:
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
    if user.role == "management":
        _mgmt_gate(user, "units")
    if user.role in ("site_manager", "management") and user.project_id:
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


def _sched_snap(payments: list) -> list:
    return [{"notes": p.get("notes") or "", "due_date": p.get("due_date"),
             "amount": round(_num(p.get("amount")), 2)}
            for p in sorted(payments, key=lambda x: x.get("seq", 0))]


async def _log_schedule(unit: dict, action: str, user: User, before: list, after: list):
    await db.schedule_logs.insert_one({
        "log_id": new_id("slog"), "unit_id": unit.get("unit_id"),
        "project_id": unit.get("project_id"), "plot_number": unit.get("plot_number"),
        "action": action, "by_user_id": user.user_id, "by_name": user.name,
        "by_role": user.role, "at": now(),
        "before": before, "after": after,
        "count_before": len(before), "count_after": len(after),
        "total_before": round(sum(_num(x.get("amount")) for x in before), 2),
        "total_after": round(sum(_num(x.get("amount")) for x in after), 2),
    })


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
    _ck = [c["key"] for c in (unit.get("columns") or []) if c.get("tag") == "charge"]
    if not _ck:
        _proj = await db.projects.find_one({"project_id": unit["project_id"]}, {"_id": 0, "columns": 1})
        _ck = [c["key"] for c in (_proj.get("columns") or []) if c.get("tag") == "charge"]
    _gt = round(sum(_num(unit.get("data", {}).get(k)) for k in _ck), 2)
    _st = round(sum(_num(row.amount) for row in payload.schedule), 2)
    if _gt > 0 and abs(_st - _gt) > 1:
        raise HTTPException(400, f"Instalments (\u20B9{_st:,.2f}) must add up to the Grand Total (\u20B9{_gt:,.2f})")
    # Optional Vault add-on: validate its schedule against the Vault total
    vault = None
    if payload.vault:
        v_total = round(_num(payload.vault.get("total")), 2)
        if v_total <= 0:
            raise HTTPException(400, "The Vault total must be greater than zero")
        v_st = round(sum(_num(r.amount) for r in payload.vault_schedule), 2)
        if not payload.vault_schedule:
            raise HTTPException(400, "The Vault schedule cannot be empty")
        if abs(v_st - v_total) > 1:
            raise HTTPException(400, f"The Vault instalments (\u20B9{v_st:,.2f}) must add up to the Vault total (\u20B9{v_total:,.2f})")
        vault = {
            "enabled": True,
            "variant_id": payload.vault.get("variant_id", ""),
            "label": payload.vault.get("label", ""),
            "construction": round(_num(payload.vault.get("construction")), 2),
            "gst": round(_num(payload.vault.get("gst")), 2),
            "total": v_total,
        }
    # Update unit
    _set = {"status": "sold",
            "buyer_name": payload.buyer_name,
            "buyer_contact": payload.buyer_contact,
            "sale_date": payload.sale_date,
            "final_price": payload.final_price,
            "booking_amount": payload.booking_amount,
            "sold_by": user.user_id,
            "sold_at": now()}
    if vault:
        _set["vault"] = vault
    await db.units.update_one({"unit_id": unit_id}, {"$set": _set})
    # Create payment records (land stream)
    docs = []
    for seq, row in enumerate(payload.schedule, start=1):
        docs.append(Payment(
            unit_id=unit_id, project_id=unit["project_id"], stream="land",
            seq=seq, due_date=row.due_date, amount=row.amount,
            notes=row.notes).model_dump())
    # Vault stream payments
    if vault:
        for seq, row in enumerate(payload.vault_schedule, start=1):
            docs.append(Payment(
                unit_id=unit_id, project_id=unit["project_id"], stream="vault",
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
    await _log_schedule({**unit, "unit_id": unit_id}, "created", user, [], _sched_snap(docs))
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
                             user: User = Depends(require_section("sales", "admin", "accounts"))):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    if user.role == "management" and user.project_id:
        q["project_id"] = user.project_id
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
    if user.role == "management":
        _mgmt_gate(user, "sales")
        if user.project_id:
            q["project_id"] = user.project_id
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


@api.put("/units/{unit_id}/schedule")
async def edit_schedule(unit_id: str, payload: ScheduleEdit,
                         user: User = Depends(require_roles("post_sales"))):
    """Post-Sales restructures a booked plot's instalment plan: edit name/due/amount,
    add or remove instalments. Guardrails: an instalment's amount can't drop below what
    is already verified, and an instalment with any recorded receipt can't be removed."""
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Plot not found")
    if unit.get("status") not in ("sold", "booked"):
        raise HTTPException(400, "Only a booked plot has a payment schedule")
    if not payload.installments:
        raise HTTPException(400, "The schedule must have at least one instalment")

    _proj = await db.projects.find_one({"project_id": unit["project_id"]}, {"_id": 0, "columns": 1})
    _ck = [c["key"] for c in (_proj.get("columns") or []) if c.get("tag") == "charge"]
    stream = payload.stream
    if stream == "vault":
        if not (unit.get("vault") or {}).get("enabled"):
            raise HTTPException(400, "This plot has no Vault add-on")
        grand_total = round(_num(unit["vault"].get("total")), 2)
    else:
        grand_total = round(sum(_num(unit.get("data", {}).get(k)) for k in _ck), 2)
    sched_total = round(sum(_num(r.amount) for r in payload.installments), 2)
    if grand_total > 0 and abs(sched_total - grand_total) > 1:
        _lbl = "Vault total" if stream == "vault" else "Grand Total"
        raise HTTPException(400, f"Instalments (\u20B9{sched_total:,.2f}) must add up to the {_lbl} (\u20B9{grand_total:,.2f})")

    existing = await db.payments.find({"unit_id": unit_id}, {"_id": 0}).to_list(500)
    existing = [p for p in existing if (p.get("stream") or "land") == stream]
    by_id = {p["payment_id"]: p for p in existing}
    incoming_ids = {r.payment_id for r in payload.installments if r.payment_id}

    def verified_of(p):
        return round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                         if r.get("verification_status") == "verified"), 2)

    for r in payload.installments:
        amt = round(_num(r.amount), 2)
        if amt <= 0:
            raise HTTPException(400, "Each instalment amount must be greater than zero")
        if r.payment_id:
            p = by_id.get(r.payment_id)
            if not p:
                raise HTTPException(400, "An instalment being edited no longer exists — reload and try again")
            v = verified_of(p)
            if amt < v - 0.01:
                raise HTTPException(400, f"'{p.get('notes') or 'instalment'}' already has \u20B9{v:,.2f} verified — its amount can't be less than that")

    to_delete = [p for pid, p in by_id.items() if pid not in incoming_ids]
    for p in to_delete:
        if p.get("receipts"):
            raise HTTPException(400, f"Can't remove '{p.get('notes') or 'instalment'}' — it has recorded payments. Return/void those receipts first.")

    if to_delete:
        await db.payments.delete_many({"payment_id": {"$in": [p["payment_id"] for p in to_delete]}})

    for seq, r in enumerate(payload.installments, start=1):
        amt = round(_num(r.amount), 2)
        if r.payment_id and r.payment_id in by_id:
            p = {**by_id[r.payment_id], "seq": seq, "due_date": r.due_date,
                 "amount": amt, "notes": r.notes or ""}
            derived = _recompute_payment(p)
            await db.payments.update_one({"payment_id": r.payment_id},
                {"$set": {"seq": seq, "due_date": r.due_date, "amount": amt,
                          "notes": r.notes or "", **derived}})
        else:
            doc = Payment(unit_id=unit_id, project_id=unit["project_id"], seq=seq, stream=stream,
                          due_date=r.due_date, amount=amt, notes=r.notes or "").model_dump()
            await db.payments.insert_one(doc)

    total = round(sum(_num(r.amount) for r in payload.installments), 2)
    after_snap = [{"notes": r.notes or "",
                   "due_date": r.due_date,
                   "amount": round(_num(r.amount), 2)} for r in payload.installments]
    await _log_schedule(unit, "edited", user, _sched_snap(existing), after_snap)

    # If any PAID instalment (has receipts) was changed, raise a revision for Accounts
    # to recheck & approve. "Paid" = has at least one receipt of any status.
    affected = []
    for r in payload.installments:
        if not r.payment_id:
            continue
        prev = by_id.get(r.payment_id)
        if not prev or not prev.get("receipts"):
            continue
        new_amt = round(_num(r.amount), 2)
        old_amt = round(_num(prev.get("amount")), 2)
        old_due = prev.get("due_date")
        old_notes = prev.get("notes") or ""
        if abs(new_amt - old_amt) > 0.01 or old_due != r.due_date or old_notes != (r.notes or ""):
            affected.append({
                "payment_id": r.payment_id, "notes": r.notes or prev.get("notes") or "",
                "before": {"amount": old_amt, "due_date": old_due, "notes": old_notes},
                "after": {"amount": new_amt, "due_date": r.due_date, "notes": r.notes or ""},
                "receipts": len(prev.get("receipts", [])),
                "verified": round(sum(_num(x.get("amount")) for x in prev.get("receipts", [])
                                      if x.get("verification_status") == "verified"), 2),
            })
    revision_raised = bool(affected)
    if revision_raised:
        rev = {
            "revision_id": new_id("srev"), "unit_id": unit_id, "project_id": unit["project_id"],
            "plot_number": unit.get("plot_number"), "buyer_name": unit.get("buyer_name") or "",
            "revised_by": user.user_id, "revised_by_name": user.name, "revised_by_role": user.role,
            "revised_at": now(), "status": "pending_review",
            "before": _sched_snap(existing), "after": after_snap,
            "affected": affected, "schedule_total": total,
            "reviewed_by": None, "reviewed_by_name": None, "reviewed_at": None, "review_note": None,
        }
        await db.schedule_revisions.insert_one(rev)
        await notify_role("accounts", "schedule_revision",
                          f"Schedule revised on PAID plot {unit.get('plot_number')} · {len(affected)} paid instalment(s) changed — recheck & approve", "/sales")

    if revision_raised:
        pass
    else:
        await notify_role("accounts", "schedule_updated",
                          f"Schedule updated · Plot {unit.get('plot_number')} · {len(payload.installments)} instalment(s) · \u20B9{total:,.0f}", "/sales")
    await notify_role("admin", "schedule_updated",
                      f"Schedule updated · Plot {unit.get('plot_number')} by {user.name}", "/sales")
    return {"ok": True, "count": len(payload.installments), "schedule_total": total,
            "revision_raised": revision_raised}


@api.get("/schedule-revisions")
async def list_schedule_revisions(status: Optional[str] = None, project_id: Optional[str] = None,
                                  user: User = Depends(require_roles("accounts", "admin"))):
    q: dict = {}
    if status:
        q["status"] = status
    if project_id:
        q["project_id"] = project_id
    revs = await db.schedule_revisions.find(q, {"_id": 0}).to_list(1000)
    revs.sort(key=lambda x: x.get("revised_at", ""), reverse=True)
    return revs


@api.post("/schedule-revisions/{revision_id}/review")
async def review_schedule_revision(revision_id: str, payload: dict = Body(default={}),
                                   user: User = Depends(require_roles("accounts", "admin"))):
    rev = await db.schedule_revisions.find_one({"revision_id": revision_id}, {"_id": 0})
    if not rev:
        raise HTTPException(404, "Revision not found")
    if rev.get("status") == "approved":
        raise HTTPException(400, "This revision is already approved")
    await db.schedule_revisions.update_one({"revision_id": revision_id}, {"$set": {
        "status": "approved", "reviewed_by": user.user_id, "reviewed_by_name": user.name,
        "reviewed_at": now(), "review_note": (payload or {}).get("note") or "",
    }})
    await notify_role("post_sales", "schedule_revision_approved",
                      f"Schedule revision approved · Plot {rev.get('plot_number')} by {user.name}", "/sales")
    return {"ok": True}


@api.get("/units/{unit_id}/schedule-log")
async def schedule_log(unit_id: str,
                        user: User = Depends(require_roles("admin", "accounts", "post_sales", "management"))):
    logs = await db.schedule_logs.find({"unit_id": unit_id}, {"_id": 0}).to_list(500)
    logs.sort(key=lambda x: x.get("at", ""), reverse=True)
    return logs


async def _plot_grand_total(unit: dict) -> float:
    """Grand Total = sum of the project's charge-tagged columns on the unit."""
    ck = [c["key"] for c in (unit.get("columns") or []) if c.get("tag") == "charge"]
    if not ck:
        proj = await db.projects.find_one({"project_id": unit["project_id"]}, {"_id": 0, "columns": 1})
        ck = [c["key"] for c in ((proj or {}).get("columns") or []) if c.get("tag") == "charge"]
    return round(sum(_num(unit.get("data", {}).get(k)) for k in ck), 2)


def _verified_of(p: dict) -> float:
    return round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                     if r.get("verification_status") == "verified"), 2)


@api.get("/mismatched-plots")
async def mismatched_plots(project_id: Optional[str] = None,
                           user: User = Depends(require_roles("admin", "post_sales"))):
    """Sold plots whose instalment schedule total does not equal the plot's Grand Total,
    so they can be snapped back into balance. Returns each plot's instalments too."""
    q = {"status": "sold"}
    if project_id:
        q["project_id"] = project_id
    pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
        {}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
    units = await db.units.find(q, {"_id": 0}).to_list(8000)
    items, grand = [], 0.0
    for u in units:
        land_gt = await _plot_grand_total(u)
        vault = u.get("vault") or {}
        streams = [("land", land_gt, "Land")]
        if vault.get("enabled"):
            streams.append(("vault", round(_num(vault.get("total")), 2), "The Vault"))
        allpays = await db.payments.find({"unit_id": u["unit_id"]}, {"_id": 0}).to_list(500)
        for skey, gt, slabel in streams:
            if gt <= 0:
                continue
            pays = [p for p in allpays if (p.get("stream") or "land") == skey]
            pays.sort(key=lambda x: x.get("seq", 0))
            sched_total = round(sum(_num(p.get("amount")) for p in pays), 2)
            diff = round(gt - sched_total, 2)
            if abs(diff) <= 1:
                continue
            grand += abs(diff)
            items.append({
                "unit_id": u["unit_id"], "plot_number": u.get("plot_number", "?"),
                "buyer_name": u.get("buyer_name") or "", "project_id": u.get("project_id"),
                "project": pnames.get(u.get("project_id"), "\u2014"),
                "stream": skey, "stream_label": slabel,
                "grand_total": gt, "schedule_total": sched_total, "difference": diff,
                "installments": [{
                    "payment_id": p["payment_id"], "notes": p.get("notes") or "",
                    "due_date": p.get("due_date"), "amount": round(_num(p.get("amount")), 2),
                    "verified": _verified_of(p),
                } for p in pays],
            })
    items.sort(key=lambda x: -abs(x["difference"]))
    return {"total": round(grand, 2), "count": len(items), "items": items}


@api.post("/units/{unit_id}/auto-fit-schedule")
async def auto_fit_schedule(unit_id: str, payload: AutoFitRequest,
                            user: User = Depends(require_roles("admin", "post_sales"))):
    """Snap the schedule to the Grand Total by adjusting the chosen instalment by the
    exact difference. Blocked if that would push it below its verified received amount."""
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Plot not found")
    if unit.get("status") != "sold":
        raise HTTPException(400, "Only a booked plot has a payment schedule")
    gt = await _plot_grand_total(unit)
    if gt <= 0:
        raise HTTPException(400, "This plot has no Grand Total to fit to")
    pays = await db.payments.find({"unit_id": unit_id}, {"_id": 0}).to_list(500)
    pays.sort(key=lambda x: x.get("seq", 0))
    if not pays:
        raise HTTPException(400, "This plot has no schedule to adjust")
    target = next((p for p in pays if p["payment_id"] == payload.payment_id), None)
    if not target:
        raise HTTPException(400, "Chosen instalment no longer exists — reload and try again")
    sched_total = round(sum(_num(p.get("amount")) for p in pays), 2)
    diff = round(gt - sched_total, 2)
    if abs(diff) <= 1:
        raise HTTPException(400, "This schedule already matches the Grand Total")
    new_amount = round(_num(target.get("amount")) + diff, 2)
    v = _verified_of(target)
    if new_amount < v - 0.01:
        raise HTTPException(400, f"Can't fit onto '{target.get('notes') or 'this instalment'}': it already has \u20B9{v:,.2f} verified, and snapping would drop it to \u20B9{new_amount:,.2f}. Pick another instalment or restructure the schedule.")
    if new_amount <= 0:
        raise HTTPException(400, f"Snapping onto '{target.get('notes') or 'this instalment'}' would make it \u20B9{new_amount:,.2f}. Pick another instalment.")
    before = _sched_snap(pays)
    updated = {**target, "amount": new_amount}
    derived = _recompute_payment(updated)
    await db.payments.update_one({"payment_id": target["payment_id"]},
        {"$set": {"amount": new_amount, **derived}})
    after = [{"notes": p.get("notes") or "", "due_date": p.get("due_date"),
              "amount": new_amount if p["payment_id"] == target["payment_id"] else round(_num(p.get("amount")), 2)}
             for p in pays]
    await _log_schedule(unit, "edited", user, before, after)
    await notify_role("accounts", "schedule_updated",
                      f"Schedule auto-fit · Plot {unit.get('plot_number')} · '{target.get('notes') or 'instalment'}' → \u20B9{new_amount:,.0f}", "/sales")
    await notify_role("admin", "schedule_updated",
                      f"Schedule auto-fit to Grand Total · Plot {unit.get('plot_number')} by {user.name}", "/sales")
    return {"ok": True, "grand_total": gt, "schedule_total": gt,
            "adjusted": {"payment_id": target["payment_id"], "notes": target.get("notes") or "",
                         "old_amount": round(_num(target.get("amount")), 2), "new_amount": new_amount}}


def _recompute_payment(pay: dict) -> dict:
    """Derive paid_amount/status from VERIFIED receipts only."""
    receipts = pay.get("receipts", [])
    verified = round(sum(_num(r.get("amount")) for r in receipts
                         if r.get("verification_status") == "verified"), 2)
    amt = round(_num(pay.get("amount")), 2)
    status = "received" if verified >= amt - 0.01 and amt > 0 else ("partial" if verified > 0 else "pending")
    last_v = [r for r in receipts if r.get("verification_status") == "verified"]
    return {
        "paid_amount": verified,
        "status": status,
        "received_date": (last_v[-1].get("date") if last_v else None),
    }


@api.post("/payments/{payment_id}/receipt")
async def add_receipt(payment_id: str, payload: ReceiptCreate,
                       user: User = Depends(require_roles("post_sales"))):
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    amt = round(_num(payload.amount), 2)
    if amt <= 0:
        raise HTTPException(400, "Payment amount must be greater than zero")
    allocs = [{"key": a.get("key", ""), "label": a.get("label", ""),
               "amount": round(_num(a.get("amount")), 2)} for a in payload.allocations]
    alloc_total = round(sum(a["amount"] for a in allocs), 2)
    if allocs and abs(alloc_total - amt) > 0.01:
        raise HTTPException(400, f"Component allocation (\u20B9{alloc_total:,.2f}) must equal amount received (\u20B9{amt:,.2f})")
    if not payload.mode:
        raise HTTPException(400, "Mode of payment is required")
    receipt = {
        "receipt_id": new_id("rc"),
        "amount": amt,
        "date": payload.date or datetime.now(timezone.utc).date().isoformat(),
        "notes": payload.notes or "",
        "mode": payload.mode, "head": payload.head or "",
        "allocations": allocs,
        "expected_remaining_date": payload.expected_remaining_date or None,
        "verification_status": "pending",
        "submitted_by": user.user_id, "submitted_by_name": user.name,
        "submitted_at": now(),
        "history": [{"action": "submitted", "by_name": user.name, "at": now()}],
    }
    await db.payments.update_one({"payment_id": payment_id}, {"$push": {"receipts": receipt}})
    unit = await db.units.find_one({"unit_id": pay["unit_id"]}, {"_id": 0})
    await notify_role(
        "accounts", "payment_verification",
        f"Verify: \u20B9{amt:,.0f} reported for Plot {unit.get('plot_number')}"
        f"{(' · ' + unit.get('buyer_name')) if unit.get('buyer_name') else ''} "
        f"· {pay.get('notes') or 'instalment'}", "/sales")
    return {"ok": True, "receipt_id": receipt["receipt_id"]}


@api.post("/payments/{payment_id}/receipts/{receipt_id}/verify")
async def verify_receipt(payment_id: str, receipt_id: str, payload: VerifyDecision,
                          user: User = Depends(require_roles("accounts"))):
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    receipts = pay.get("receipts", [])
    rc = next((r for r in receipts if r.get("receipt_id") == receipt_id), None)
    if not rc:
        raise HTTPException(404, "Receipt not found")
    if rc.get("verification_status") == "verified":
        raise HTTPException(400, "This payment is already verified")
    if payload.decision == "yes":
        rc["verification_status"] = "verified"
        rc["verified_by"] = user.user_id
        rc["verified_by_name"] = user.name
        rc["verified_at"] = now()
        rc.setdefault("history", []).append({"action": "verified", "by_name": user.name, "at": now()})
    else:
        if not payload.reason:
            raise HTTPException(400, "A reason is required to return a payment")
        rc["verification_status"] = "returned"
        rc["return_reason"] = payload.reason
        rc["return_notes"] = payload.notes or ""
        rc["returned_by"] = user.user_id
        rc["returned_by_name"] = user.name
        rc["returned_at"] = now()
        rc.setdefault("history", []).append({"action": "returned", "by_name": user.name, "at": now(), "reason": payload.reason})
    derived = _recompute_payment({**pay, "receipts": receipts})
    await db.payments.update_one({"payment_id": payment_id}, {"$set": {"receipts": receipts, **derived}})
    unit = await db.units.find_one({"unit_id": pay["unit_id"]}, {"_id": 0})
    if payload.decision == "yes":
        await notify_role("admin", "payment_received",
                          f"Payment verified · Plot {unit.get('plot_number')} · \u20B9{_num(rc['amount']):,.0f}", "/sales")
        await notify(rc.get("submitted_by"), "payment_verified",
                          f"Payment verified · Plot {unit.get('plot_number')} · \u20B9{_num(rc['amount']):,.0f}", "/dashboard")
    else:
        await notify(rc.get("submitted_by"), "payment_returned",
                          f"Payment returned · Plot {unit.get('plot_number')} · {payload.reason}", "/dashboard")
    return {"ok": True, **derived}


@api.patch("/payments/{payment_id}/receipts/{receipt_id}")
async def correct_receipt(payment_id: str, receipt_id: str, payload: ReceiptCreate,
                           user: User = Depends(require_roles("post_sales"))):
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    receipts = pay.get("receipts", [])
    rc = next((r for r in receipts if r.get("receipt_id") == receipt_id), None)
    if not rc:
        raise HTTPException(404, "Receipt not found")
    if rc.get("verification_status") != "returned":
        raise HTTPException(400, "Only a returned payment can be corrected")
    amt = round(_num(payload.amount), 2)
    if amt <= 0:
        raise HTTPException(400, "Payment amount must be greater than zero")
    allocs = [{"key": a.get("key", ""), "label": a.get("label", ""),
               "amount": round(_num(a.get("amount")), 2)} for a in payload.allocations]
    alloc_total = round(sum(a["amount"] for a in allocs), 2)
    if allocs and abs(alloc_total - amt) > 0.01:
        raise HTTPException(400, f"Component allocation must equal amount received (\u20B9{amt:,.2f})")
    if not payload.mode:
        raise HTTPException(400, "Mode of payment is required")
    rc.update({
        "amount": amt, "date": payload.date or rc.get("date"),
        "notes": payload.notes or "", "mode": payload.mode, "head": payload.head or "",
        "allocations": allocs, "expected_remaining_date": payload.expected_remaining_date or None,
        "verification_status": "pending",
    })
    rc.pop("return_reason", None); rc.pop("return_notes", None)
    rc.setdefault("history", []).append({"action": "resubmitted", "by_name": user.name, "at": now()})
    await db.payments.update_one({"payment_id": payment_id}, {"$set": {"receipts": receipts}})
    unit = await db.units.find_one({"unit_id": pay["unit_id"]}, {"_id": 0})
    await notify_role("accounts", "payment_verification",
                      f"Re-verify: \u20B9{amt:,.0f} for Plot {unit.get('plot_number')} (corrected)", "/sales")
    return {"ok": True}


@api.patch("/payments/{payment_id}/receipts/{receipt_id}/allocations")
async def edit_receipt_allocations(payment_id: str, receipt_id: str, payload: AllocationEdit,
                                    user: User = Depends(require_roles("accounts"))):
    """Accounts can bifurcate/re-bifurcate an existing receipt so component
    statements reconcile at source. Does not change the receipt amount or status."""
    pay = await db.payments.find_one({"payment_id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")
    receipts = pay.get("receipts", [])
    rc = next((r for r in receipts if r.get("receipt_id") == receipt_id), None)
    if not rc:
        raise HTTPException(404, "Receipt not found")
    amt = round(_num(rc.get("amount")), 2)
    allocs = [{"key": a.get("key", ""), "label": a.get("label", ""),
               "amount": round(_num(a.get("amount")), 2)} for a in payload.allocations]
    alloc_total = round(sum(a["amount"] for a in allocs), 2)
    if not allocs:
        raise HTTPException(400, "At least one component allocation is required")
    if abs(alloc_total - amt) > 0.01:
        raise HTTPException(400, f"Component allocation (\u20B9{alloc_total:,.2f}) must equal amount received (\u20B9{amt:,.2f})")
    rc["allocations"] = allocs
    rc.setdefault("history", []).append({"action": "bifurcated", "by_name": user.name, "at": now()})
    await db.payments.update_one({"payment_id": payment_id}, {"$set": {"receipts": receipts}})
    return {"ok": True}


@api.post("/projects/{project_id}/receipts/auto-bifurcate")
async def auto_bifurcate_project(project_id: str,
                                  user: User = Depends(require_roles("accounts", "admin"))):
    """One-click reconcile: for every verified receipt in this project that has no
    stored breakdown, if its payment head clearly maps to a single component, write the
    full receipt amount to that component. Receipts with vague/blank heads are skipped
    and returned so Accounts can bifurcate them by hand."""
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    charge_cols = [c for c in (proj.get("columns") or []) if c.get("tag") == "charge"]
    label_by_key = {c.get("key"): c.get("label", c.get("key")) for c in charge_cols}
    units = await db.units.find({"project_id": project_id}, {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1}).to_list(2000)
    plot_by_unit = {u["unit_id"]: u for u in units}
    pays = await db.payments.find({"project_id": project_id}, {"_id": 0}).to_list(5000)
    mapped, skipped = 0, []
    for p in pays:
        receipts = p.get("receipts", [])
        changed = False
        for rc in receipts:
            if rc.get("verification_status") != "verified":
                continue
            if rc.get("allocations"):
                continue
            key = _map_head_to_key(rc.get("head"), charge_cols)
            amt = round(_num(rc.get("amount")), 2)
            if key:
                rc["allocations"] = [{"key": key, "label": label_by_key.get(key, key), "amount": amt}]
                rc.setdefault("history", []).append({"action": "auto_bifurcated", "by_name": user.name, "at": now()})
                mapped += 1
                changed = True
            else:
                u = plot_by_unit.get(p.get("unit_id"), {})
                skipped.append({
                    "payment_id": p.get("payment_id"), "receipt_id": rc.get("receipt_id"),
                    "unit_id": p.get("unit_id"), "plot_number": u.get("plot_number", "?"),
                    "buyer_name": u.get("buyer_name") or "", "instalment": p.get("notes") or f"#{p.get('seq')}",
                    "amount": amt, "date": rc.get("date") or "", "head": rc.get("head") or "",
                })
        if changed:
            await db.payments.update_one({"payment_id": p["payment_id"]}, {"$set": {"receipts": receipts}})
    return {"ok": True, "mapped": mapped, "skipped": len(skipped), "skipped_details": skipped}


# ----- plot-wise payment report (PDF) -------------------------------------
def _inr_plain(n) -> str:
    """Indian-grouped rupee string (Rs. prefix). Shows 2 decimals only when non-integer."""
    import re
    v = round(_num(n), 2)
    neg = v < 0
    v = abs(v)
    whole = int(v)
    frac = int(round((v - whole) * 100))
    s = str(whole)
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    if frac:
        s = s + ".%02d" % frac
    return ("-" if neg else "") + "Rs. " + s


def _num_to_words_in(n: int) -> str:
    n = int(n)
    if n == 0:
        return "Zero"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two(x):
        return ones[x] if x < 20 else tens[x // 10] + ((" " + ones[x % 10]) if x % 10 else "")

    def three(x):
        h, r = x // 100, x % 100
        s = (ones[h] + " Hundred") if h else ""
        if r:
            s += (" " if s else "") + two(r)
        return s

    parts = []
    crore, n = n // 10000000, n % 10000000
    lakh, n = n // 100000, n % 100000
    thousand, n = n // 1000, n % 1000
    if crore:
        parts.append(three(crore) + " Crore")
    if lakh:
        parts.append(two(lakh) + " Lakh")
    if thousand:
        parts.append(two(thousand) + " Thousand")
    if n:
        parts.append(three(n))
    return " ".join(parts).strip()


def _amount_words(n) -> str:
    v = round(_num(n), 2)
    rupees = int(v)
    paise = int(round((v - rupees) * 100))
    w = "Rupees " + _num_to_words_in(rupees)
    if paise:
        w += " and " + _num_to_words_in(paise) + " Paise"
    return w + " Only"


def _map_head_to_key(head, charge_cols):
    """Best-effort map a legacy receipt's payment head to a component key.
    Used only for old receipts that have no stored bifurcation."""
    h = (head or "").lower().replace("collection", "").replace("charges", "").strip()
    if not h:
        return None
    aliases = {
        "bsp": ["basic sale", "bsp"],
        "plc": ["plc", "preferential", "location"],
        "registration": ["registration"],
        "maintenance": ["maintenance"],
    }
    keys = aliases.get(h, [h])
    for c in charge_cols:
        lbl = (c.get("label") or "").lower()
        key = (c.get("key") or "").lower()
        if any(k in lbl for k in keys) or any(k in key for k in keys):
            return c.get("key")
    return None


async def _plot_report_data(unit_id: str) -> dict:
    unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Plot not found")
    proj = await db.projects.find_one({"project_id": unit["project_id"]}, {"_id": 0}) or {}
    cols = proj.get("columns") or []
    pays = await db.payments.find({"unit_id": unit_id}, {"_id": 0}).sort("seq", 1).to_list(500)

    charge_cols = [c for c in cols if c.get("tag") == "charge"]
    verified_by_key: dict = {}
    verified_receipts_total = 0.0
    unbifurcated_verified = 0.0
    history = []
    for p in pays:
        inst = p.get("notes") or f"Instalment {p.get('seq')}"
        for r in p.get("receipts", []):
            if r.get("verification_status") == "verified":
                ramt = _num(r.get("amount"))
                verified_receipts_total += ramt
                allocs = r.get("allocations", [])
                if allocs:
                    for a in allocs:
                        k = a.get("key", "")
                        verified_by_key[k] = verified_by_key.get(k, 0.0) + _num(a.get("amount"))
                else:
                    unbifurcated_verified += ramt
            history.append({
                "date": r.get("date") or "",
                "amount": round(_num(r.get("amount")), 2),
                "components": ", ".join(a.get("label", "") for a in r.get("allocations", [])) or "—",
                "mode": r.get("mode") or "—",
                "head": r.get("head") or "—",
                "installment": inst,
                "verification_status": r.get("verification_status", "pending"),
            })
    history.sort(key=lambda x: x["date"])

    components = []
    for c in cols:
        if c.get("tag") != "charge":
            continue
        amt = round(_num(unit.get("data", {}).get(c["key"])), 2)
        vr = round(verified_by_key.get(c["key"], 0.0), 2)
        if amt == 0 and vr == 0:
            continue
        components.append({"label": c.get("label", c["key"]), "amount": amt,
                           "verified": vr, "balance": round(amt - vr, 2)})

    unbifurcated_verified = round(unbifurcated_verified, 2)

    gst_components = [c for c in components if "gst" in c["label"].lower()]
    gst_total = round(sum(c["amount"] for c in gst_components), 2)

    # Total Payable is fetched from the instalment schedule (which the rep sets to equal
    # the Grand Total). Falls back to final price / stored total only if there is no schedule.
    _land_pays = [p for p in pays if (p.get("stream") or "land") != "vault"]
    _vault_pays = [p for p in pays if (p.get("stream") or "land") == "vault"]
    _sched_total = round(sum(_num(p.get("amount")) for p in _land_pays), 2)
    total_payable = _sched_total if _sched_total > 0 else round(_num(unit.get("final_price")) or _num(unit.get("total")), 2)
    plan, verified_total, awaiting_total = [], 0.0, 0.0
    for p in _land_pays:
        exp = round(_num(p.get("amount")), 2)
        rec = round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                        if r.get("verification_status") == "verified"), 2)
        awaiting = round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                             if r.get("verification_status") == "pending"), 2)
        verified_total += rec
        awaiting_total += awaiting
        plan.append({"installment": p.get("notes") or f"Instalment {p.get('seq')}",
                     "due": p.get("due_date") or "—", "expected": exp, "received": rec,
                     "balance": round(exp - rec, 2), "status": p.get("status", "pending")})
    verified_total = round(verified_total, 2)
    awaiting_total = round(awaiting_total, 2)
    outstanding = round(total_payable - verified_total, 2)

    # The Vault add-on: its own schedule + totals (only present when opted in)
    vault_meta = unit.get("vault") or {}
    vault_plan, vault_verified = [], 0.0
    for p in _vault_pays:
        exp = round(_num(p.get("amount")), 2)
        rec = round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                        if r.get("verification_status") == "verified"), 2)
        vault_verified += rec
        vault_plan.append({"installment": p.get("notes") or f"Instalment {p.get('seq')}",
                           "due": p.get("due_date") or "—", "expected": exp, "received": rec,
                           "balance": round(exp - rec, 2), "status": p.get("status", "pending")})
    vault_total = round(_num(vault_meta.get("total")), 2) if vault_meta.get("enabled") else 0.0
    vault = {
        "enabled": bool(vault_meta.get("enabled")) and len(_vault_pays) > 0,
        "label": vault_meta.get("label", ""),
        "construction": round(_num(vault_meta.get("construction")), 2),
        "gst": round(_num(vault_meta.get("gst")), 2),
        "total": vault_total,
        "verified": round(vault_verified, 2),
        "outstanding": round(vault_total - vault_verified, 2),
        "plan": vault_plan,
    }

    pending_rows = [p for p in pays if p.get("status") != "received"]
    next_due, next_due_date = None, None
    if pending_rows:
        nd = sorted(pending_rows, key=lambda x: x.get("due_date") or "z")[0]
        nd_rec = round(sum(_num(r.get("amount")) for r in nd.get("receipts", [])
                           if r.get("verification_status") == "verified"), 2)
        next_due = round(_num(nd.get("amount")) - nd_rec, 2)
        next_due_date = nd.get("due_date")

    expected_remaining = [{"amount": round(_num(r.get("amount")), 2),
                           "date": r.get("expected_remaining_date")}
                          for p in pays for r in p.get("receipts", [])
                          if r.get("expected_remaining_date")
                          and r.get("verification_status") in ("pending", "verified")]
    upcoming = [{"installment": p.get("notes") or f"Instalment {p.get('seq')}",
                 "due": p.get("due_date"), "balance": round(_num(p.get("amount")) - _num(p.get("paid_amount")), 2)}
                for p in pays if p.get("status") != "received"]

    return {
        "project_name": proj.get("name", ""),
        "plot_number": unit.get("plot_number", "?"),
        "customer": unit.get("buyer_name") or "—",
        "booking_date": unit.get("sale_date") or (unit.get("sold_at") or "")[:10] or "—",
        "total_payable": total_payable,
        "verified_received": verified_total,
        "outstanding": outstanding,
        "awaiting_verification": awaiting_total,
        "next_due": next_due,
        "next_due_date": next_due_date or "—",
        "components": components,
        "unbifurcated_verified": unbifurcated_verified,
        "gst_components": gst_components,
        "gst_total": gst_total,
        "plan": plan,
        "vault": vault,
        "history": history,
        "expected_remaining": expected_remaining,
        "upcoming": upcoming,
    }


def _build_report_pdf(d: dict) -> bytes:
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, Image as RLImage, HRFlowable)

    OLIVE = colors.HexColor("#5a6b10")
    INK = colors.HexColor("#2b2b26")
    MUTE = colors.HexColor("#6b6b60")
    CREAM = colors.HexColor("#f4f2e8")
    BORDER = colors.HexColor("#d9d6c6")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"Payment Report - Plot {d['plot_number']}")
    W = doc.width
    H = lambda t: Paragraph(t, ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11,
                            textColor=OLIVE, spaceBefore=10, spaceAfter=5, leading=13))
    small = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11)
    story = []

    pname = (d.get("project_name") or "").lower()
    if "central vista" in pname:
        logo_path = "/app/frontend/public/proj-cvf.png"
    elif "vacation village" in pname:
        logo_path = "/app/frontend/public/proj-vv.png"
    else:
        logo_path = "/app/frontend/public/report-logo.png"
    brand = []
    if os.path.exists(logo_path):
        try:
            img = RLImage(logo_path)
            img._restrictSize(62 * mm, 28 * mm)
            brand.append(img)
        except Exception:
            pass
    head = Table([[brand or ""]], colWidths=[W])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("ALIGN", (0, 0), (0, 0), "CENTER")]))
    story += [head, Spacer(1, 6), HRFlowable(width="100%", color=OLIVE, thickness=1.4), Spacer(1, 8)]

    # Document title band
    doc_title = Table([[
        Paragraph("PAYMENT STATEMENT", ParagraphStyle("dt", fontName="Helvetica-Bold",
                  fontSize=13, textColor=OLIVE, leading=15)),
        Paragraph(f"Statement date: {datetime.now(timezone.utc).strftime('%d %b %Y')}",
                  ParagraphStyle("dd", fontName="Helvetica", fontSize=8.5, textColor=MUTE)),
    ]], colWidths=[W * 0.62, W * 0.38])
    doc_title.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                   ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story += [doc_title,
              Paragraph(f"{d['project_name']} &nbsp;·&nbsp; Plot {d['plot_number']} &nbsp;·&nbsp; {d['customer']}",
                        ParagraphStyle("dsub", fontName="Helvetica", fontSize=9.5, textColor=INK, spaceBefore=2)),
              Spacer(1, 4)]

    # Plot Information
    story.append(H("Plot Information"))
    info = [["Project", d["project_name"], "Booking Date", d["booking_date"]],
            ["Plot", d["plot_number"], "Customer", d["customer"]]]
    t = Table(info, colWidths=[W * 0.16, W * 0.34, W * 0.18, W * 0.32])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTE), ("TEXTCOLOR", (2, 0), (2, -1), MUTE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER)]))
    story.append(t)

    # Payment Summary
    story.append(H("Payment Summary"))
    sm = [["Total Payable", _inr_plain(d["total_payable"]), "Verified Received", _inr_plain(d["verified_received"])],
          ["Outstanding", _inr_plain(d["outstanding"]), "Awaiting Verification", _inr_plain(d["awaiting_verification"])],
          ["Next Due", _inr_plain(d["next_due"]) if d["next_due"] is not None else "—", "Next Due Date", str(d["next_due_date"])]]
    t = Table(sm, colWidths=[W * 0.22, W * 0.28, W * 0.26, W * 0.24])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTE), ("TEXTCOLOR", (2, 0), (2, -1), MUTE),
        ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 9.5), ("FONT", (3, 0), (3, -1), "Helvetica-Bold", 9.5),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
    story.append(t)
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Total payable in words:</b> {_amount_words(d['total_payable'])}",
                 ParagraphStyle("words", fontName="Helvetica-Oblique", fontSize=9,
                                textColor=INK, leading=12, spaceBefore=2)))

    def money_table(title, header, rows, aligns=None, widths=None):
        story.append(H(title))
        if not rows:
            story.append(Paragraph("No data.", small)); return
        data = [header] + rows
        tt = Table(data, colWidths=widths, repeatRows=1)
        st = [("BACKGROUND", (0, 0), (-1, 0), OLIVE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
              ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
              ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
        for col in (aligns or []):
            st.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
        tt.setStyle(TableStyle(st))
        story.append(tt)

    # Component Structure
    money_table("Component Structure",
                ["Component", "Amount", "Verified Received", "Balance"],
                [[c["label"], _inr_plain(c["amount"]), _inr_plain(c["verified"]), _inr_plain(c["balance"])]
                 for c in d["components"]],
                aligns=[1, 2, 3], widths=[W * 0.40, W * 0.20, W * 0.20, W * 0.20])
    if d.get("unbifurcated_verified", 0) > 0.01:
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            f"Note: {_inr_plain(d['unbifurcated_verified'])} of verified receipts is not yet "
            f"bifurcated across components and is therefore not shown in the rows above.",
            small))

    # Tax Summary (GST)
    if d.get("gst_components"):
        story.append(H("Tax Summary (GST)"))
        grows = [[c["label"], _inr_plain(c["amount"])] for c in d["gst_components"]]
        grows.append(["Total GST", _inr_plain(d["gst_total"])])
        gt = Table([["GST Component", "Amount"]] + grows, colWidths=[W * 0.60, W * 0.40])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), OLIVE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, -1), (-1, -1), CREAM),
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9),
            ("LINEABOVE", (0, -1), (-1, -1), 0.6, OLIVE)]))
        story.append(gt)

    # Payment Plan (Land)
    _v = d.get("vault") or {}
    _has_vault = _v.get("enabled")
    money_table("Payment Plan" + (" — Land" if _has_vault else ""),
                ["Installment", "Due Date", "Expected", "Received", "Balance", "Status"],
                [[p["installment"], str(p["due"]), _inr_plain(p["expected"]), _inr_plain(p["received"]),
                  _inr_plain(p["balance"]), p["status"].title()] for p in d["plan"]],
                aligns=[2, 3, 4], widths=[W * 0.26, W * 0.16, W * 0.15, W * 0.15, W * 0.15, W * 0.13])

    # The Vault — optional construction add-on with its own schedule
    if _has_vault:
        story.append(H("The Vault — Construction Add-on"))
        story.append(Paragraph(
            f"<b>{_v.get('label','')}</b> &nbsp;·&nbsp; Construction {_inr_plain(_v.get('construction',0))} "
            f"+ GST {_inr_plain(_v.get('gst',0))} = <b>Total {_inr_plain(_v.get('total',0))}</b> &nbsp;·&nbsp; "
            f"Verified Received {_inr_plain(_v.get('verified',0))} &nbsp;·&nbsp; Outstanding {_inr_plain(_v.get('outstanding',0))}",
            small))
        story.append(Spacer(1, 4))
        money_table("The Vault — Payment Plan",
                    ["Installment", "Due Date", "Expected", "Received", "Balance", "Status"],
                    [[p["installment"], str(p["due"]), _inr_plain(p["expected"]), _inr_plain(p["received"]),
                      _inr_plain(p["balance"]), p["status"].title()] for p in _v.get("plan", [])],
                    aligns=[2, 3, 4], widths=[W * 0.26, W * 0.16, W * 0.15, W * 0.15, W * 0.15, W * 0.13])

    # Actual Payment History
    money_table("Actual Payment History",
                ["Received Date", "Amount", "Components", "Mode", "Payment Head", "Verification"],
                [[str(h["date"]), _inr_plain(h["amount"]), h["components"], h["mode"], h["head"],
                  h["verification_status"].title()] for h in d["history"]],
                aligns=[1], widths=[W * 0.15, W * 0.15, W * 0.26, W * 0.13, W * 0.16, W * 0.15])

    # Pending Details
    story.append(H("Pending Details"))
    story.append(Paragraph(f"<b>Outstanding:</b> {_inr_plain(d['outstanding'])} &nbsp;&nbsp; "
                           f"<b>Awaiting Verification:</b> {_inr_plain(d['awaiting_verification'])}", small))
    if d["expected_remaining"]:
        story.append(Spacer(1, 3))
        story.append(Paragraph("Expected remaining payments (from partial payments):", small))
        for e in d["expected_remaining"]:
            story.append(Paragraph(f"• {_inr_plain(e['amount'])} expected by {e['date'] or '—'}", small))
    if d["upcoming"]:
        story.append(Spacer(1, 3))
        story.append(Paragraph("Upcoming dues:", small))
        for u in d["upcoming"]:
            story.append(Paragraph(f"• {u['installment']} — {_inr_plain(u['balance'])} due {u['due'] or '—'}", small))

    story += [Spacer(1, 14), HRFlowable(width="100%", color=BORDER, thickness=0.6), Spacer(1, 4),
              Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y')} · This is a computer-generated statement. Verified figures reflect Accounts-confirmed receipts only.",
                        ParagraphStyle("f", fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTE))]
    doc.build(story)
    return buf.getvalue()


@api.get("/units/{unit_id}/payment-report")
async def download_payment_report(unit_id: str,
                                  user: User = Depends(require_report_access())):
    data = await _plot_report_data(unit_id)
    pdf = _build_report_pdf(data)
    safe = "".join(ch for ch in str(data["plot_number"]) if ch.isalnum() or ch in "-_") or "plot"
    from fastapi.responses import Response
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Payment_Report_{safe}.pdf"'})


@api.get("/projects/{project_id}/payment-reports.zip")
async def bulk_payment_reports(project_id: str,
                               user: User = Depends(require_report_access())):
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    units = await db.units.find(
        {"project_id": project_id, "status": "sold"},
        {"_id": 0, "unit_id": 1, "plot_number": 1}).to_list(5000)
    if not units:
        raise HTTPException(404, "No sold plots in this project")
    import io, zipfile, re, asyncio
    used, zbuf = set(), io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
        for u in units:
            try:
                data = await _plot_report_data(u["unit_id"])
                pdf = await asyncio.to_thread(_build_report_pdf, data)
            except Exception:
                continue
            safe = re.sub(r"[^A-Za-z0-9\-_]", "_", str(u.get("plot_number") or u["unit_id"])) or "plot"
            name, i = f"Payment_Report_{safe}.pdf", 1
            while name in used:
                name = f"Payment_Report_{safe}_{i}.pdf"; i += 1
            used.add(name)
            zf.writestr(name, pdf)
    proj_safe = re.sub(r"[^A-Za-z0-9\-_]", "_", proj.get("name", "project")) or "project"
    from fastapi.responses import Response
    return Response(content=zbuf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="Payment_Reports_{proj_safe}.zip"'})



@api.get("/payments/verifications")
async def payment_verifications(status: Optional[str] = None,
                                 user: User = Depends(require_section("sales", "accounts", "admin"))):
    """Flatten pending/returned/verified receipts with booking context for the queue."""
    scope = {"receipts.0": {"$exists": True}}
    if user.role == "management" and user.project_id:
        scope["project_id"] = user.project_id
    projects = {p["project_id"]: p for p in await db.projects.find({}, {"_id": 0}).to_list(100)}
    units_map = {u["unit_id"]: u for u in await db.units.find(
        {}, {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1}).to_list(5000)}
    out = []
    async for pay in db.payments.find(scope, {"_id": 0}):
        unit = units_map.get(pay["unit_id"])
        for rc in pay.get("receipts", []):
            vs = rc.get("verification_status", "verified")
            if status and vs != status:
                continue
            out.append({
                "payment_id": pay["payment_id"], "receipt_id": rc.get("receipt_id"),
                "project_id": pay["project_id"],
                "project_name": projects.get(pay["project_id"], {}).get("name", ""),
                "plot_number": unit.get("plot_number") if unit else "",
                "buyer_name": unit.get("buyer_name") if unit else "",
                "instalment": pay.get("notes"), "due_date": pay.get("due_date"),
                "expected_amount": pay.get("amount"),
                "amount": rc.get("amount"), "date": rc.get("date"),
                "mode": rc.get("mode"), "head": rc.get("head"),
                "allocations": rc.get("allocations", []),
                "expected_remaining_date": rc.get("expected_remaining_date"),
                "notes": rc.get("notes"), "verification_status": vs,
                "submitted_by_name": rc.get("submitted_by_name"), "submitted_at": rc.get("submitted_at"),
                "return_reason": rc.get("return_reason"), "return_notes": rc.get("return_notes"),
                "history": rc.get("history", []),
            })
    out.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)
    return out


# ----- procurement (site_manager -> admin -> accounts) -------------------
@api.get("/accounts/overview")
async def accounts_overview(user: User = Depends(require_section("sales", "accounts", "admin", "post_sales"))):
    scope: dict = {}
    if user.role == "management" and user.project_id:
        scope = {"project_id": user.project_id}
    payments = await db.payments.find(scope, {"_id": 0}).to_list(20000)
    units = await db.units.find(
        {**scope, "status": "sold"},
        {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1, "project_id": 1}).to_list(5000)
    umap = {u["unit_id"]: u for u in units}
    projects = await db.projects.find(scope, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)
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
    if user.role in ("site_manager", "management") and user.project_id:
        q["project_id"] = user.project_id
    if user.role == "management":
        _mgmt_gate(user, "procurement")
    return await db.procurement.find(q, {"_id": 0}).sort("requested_at", -1).to_list(500)


@api.post("/procurement")
async def create_procurement(
        project_id: str = Form(...),
        subject: str = Form(...),
        items: str = Form(...),
        priority: str = Form("medium"),
        notes: str = Form(""),
        pi_amount: float = Form(0),
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
        priority=priority, notes=notes, pi_amount=pi_amount,
        requested_by=user.user_id, pi_file=pi_ref,
        status="pending_admin")
    await db.procurement.insert_one(r.model_dump())
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0}) or {}
    await notify_role("admin", "procurement_new",
                      f"Procurement request · {subject} · {proj.get('name','')} · "
                      f"Priority: {priority} — needs your approval", "/procurement")
    return r.model_dump()


@api.post("/procurement/{request_id}/po")
async def issue_po(request_id: str,
                    po_number: str = Form(...),
                    note: str = Form(""),
                    file: Optional[UploadFile] = File(None),
                    user: User = Depends(require_roles("accounts", "admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] not in ("approved", "po_issued"):
        raise HTTPException(400, "Only approved requests can get a PO")
    po_ref = await save_upload(file, "procurement/po", user.user_id) if file else doc.get("po_file")
    await db.procurement.update_one({"request_id": request_id}, {"$set": {
        "status": "po_issued", "po_number": po_number, "po_file": po_ref, "accounts_note": note}})
    await notify(doc["requested_by"], "procurement_po",
                 f"PO issued for '{doc['subject']}' · PO {po_number}"
                 + (f" · Note: {note}" if note else ""), "/procurement")
    await notify_role("admin", "procurement_po",
                      f"PO {po_number} issued · {doc['subject']}", "/procurement")
    return {"ok": True, "status": "po_issued"}


@api.post("/procurement/{request_id}/tax-invoice")
async def upload_tax_invoice(request_id: str,
                             file: UploadFile = File(...),
                             user: User = Depends(require_roles("site_manager", "accounts", "admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if user.role == "site_manager" and doc.get("requested_by") != user.user_id:
        raise HTTPException(403, "Not your request")
    ref = await save_upload(file, "procurement/tax_invoice", user.user_id)
    await db.procurement.update_one({"request_id": request_id}, {"$set": {"tax_invoice_file": ref}})
    await notify_role("accounts", "procurement_tax_invoice",
                      f"Tax invoice uploaded · {doc['subject']}", "/procurement")
    await notify_role("admin", "procurement_tax_invoice",
                      f"Tax invoice uploaded · {doc['subject']}", "/procurement")
    return {"ok": True, "tax_invoice_file": ref}


@api.post("/procurement/{request_id}/resubmit-pi")
async def resubmit_pi(request_id: str,
                      notes: str = Form(""),
                      pi_amount: float = Form(0),
                      items: str = Form(""),
                      file: Optional[UploadFile] = File(None),
                      user: User = Depends(require_roles("site_manager", "admin"))):
    """Site manager re-uploads a fresh PI after Admin asks for one or rejects it (request stays open)."""
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if user.role == "site_manager" and doc.get("requested_by") != user.user_id:
        raise HTTPException(403, "Not your request")
    if doc["status"] not in ("pending_clarification", "pending_admin", "management_clarification",
                             "pending_management", "rejected"):
        raise HTTPException(400, "This request can no longer be revised")
    upd = {"status": "pending_admin"}
    push = None
    # Archive the current PI (and the reason it was rejected/returned) so admins can
    # always review previously rejected documents, even after a later version is approved.
    if file and doc.get("pi_file"):
        push = {"pi_history": {
            "pi_file": doc["pi_file"],
            "pi_amount": doc.get("pi_amount"),
            "items": doc.get("items", []),
            "notes": doc.get("notes", ""),
            "outcome": doc["status"],
            "admin_note": doc.get("admin_note", ""),
            "mgmt_note": doc.get("mgmt_note", ""),
            "archived_at": now(),
        }}
    if file:
        upd["pi_file"] = await save_upload(file, "procurement/pi", user.user_id)
    if notes:
        upd["notes"] = notes
    if pi_amount:
        upd["pi_amount"] = pi_amount
    if items:
        try:
            upd["items"] = [ProcurementItem(**i).model_dump() for i in json.loads(items)]
        except Exception:
            raise HTTPException(400, "Invalid items payload")
    mongo_update = {"$set": upd}
    if push:
        mongo_update["$push"] = push
    await db.procurement.update_one({"request_id": request_id}, mongo_update)
    await notify_role("admin", "procurement_new",
                      f"Revised PI submitted · {doc['subject']} — needs your approval", "/procurement")
    return {"ok": True, "status": "pending_admin"}


@api.post("/procurement/{request_id}/replace-file")
async def replace_file(request_id: str,
                       doc_type: str = Form(...),
                       file: UploadFile = File(...),
                       user: User = Depends(require_roles("site_manager", "admin", "accounts"))):
    """Re-attach a document (PI / PO / Tax Invoice) on a request without changing its workflow
    status — used to re-upload files whose old (external) storage object was lost."""
    field_map = {"pi": ("pi_file", "procurement/pi"),
                 "po": ("po_file", "procurement/po"),
                 "tax": ("tax_invoice_file", "procurement/tax")}
    if doc_type not in field_map:
        raise HTTPException(400, "Invalid document type")
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    # Permissions: PI belongs to the site manager (own) or admin; PO/Tax to accounts or admin.
    if doc_type == "pi":
        if user.role not in ("site_manager", "admin"):
            raise HTTPException(403, "Not allowed")
        if user.role == "site_manager" and doc.get("requested_by") != user.user_id:
            raise HTTPException(403, "Not your request")
    else:
        if user.role not in ("accounts", "admin"):
            raise HTTPException(403, "Not allowed")
    field, folder = field_map[doc_type]
    ref = await save_upload(file, folder, user.user_id)
    await db.procurement.update_one({"request_id": request_id}, {"$set": {field: ref}})
    return {"ok": True, "doc_type": doc_type, "file": ref}


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
    fname = rec.get("original_filename") or "file"
    ctype = rec.get("content_type", "application/octet-stream")

    # New files live in MongoDB GridFS.
    if rec.get("gridfs_id"):
        try:
            stream = await fs_bucket.open_download_stream(ObjectId(rec["gridfs_id"]))
            data = await stream.read()
        except Exception as e:
            log.error("GridFS read failed file=%s gid=%s err=%s", file_id, rec.get("gridfs_id"), e)
            raise HTTPException(404, "This file could not be read. Please re-upload it and try again.")
        return Response(content=data, media_type=ctype,
                        headers={"Content-Disposition": f'inline; filename="{fname}"'})

    # Legacy files stored in the external object-storage service.
    if not rec.get("storage_path"):
        raise HTTPException(404, "This attachment has no stored file. Please re-upload it.")
    try:
        data, octype = get_object(rec["storage_path"])
    except StorageError as e:
        log.error("Attachment fetch failed file=%s path=%s status=%s body=%s",
                  file_id, rec.get("storage_path"), e.status, e.body[:300])
        if e.status in (402, 403):
            raise HTTPException(503, "File storage is temporarily unavailable for this account "
                                     "(billing/key). Please contact the administrator.")
        raise HTTPException(502, "This file was uploaded on the old storage and can no longer be "
                                 "retrieved. Please re-upload it — new uploads are stored reliably.")
    except Exception as e:
        log.error("Attachment fetch crashed file=%s path=%s err=%s",
                  file_id, rec.get("storage_path"), e)
        raise HTTPException(502, "This file was uploaded on the old storage and can no longer be "
                                 "retrieved. Please re-upload it.")
    return Response(content=data, media_type=ctype,
                    headers={"Content-Disposition": f'inline; filename="{fname}"'})


@api.post("/procurement/{request_id}/action")
async def admin_action_procurement(request_id: str, payload: AdminAction,
                                    user: User = Depends(require_roles("admin"))):
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] not in ("pending_admin", "pending_clarification"):
        raise HTTPException(400, f"Cannot act on request in status {doc['status']}")
    mgmt = None
    if payload.action == "approve":
        # New flow: Admin approval sends the request straight to Accounts.
        # Management is notified for parallel (optional, non-gating) review.
        mgmt = await db.users.find_one(
            {"role": "management", "project_id": doc["project_id"], "is_active": True},
            {"_id": 0, "user_id": 1})
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
    proj = await db.projects.find_one({"project_id": doc["project_id"]}, {"_id": 0}) or {}
    if new_status == "approved":
        await notify_role("accounts", "procurement_approved",
                          f"Approved procurement ready for PO/payment · "
                          f"{doc['subject']}", "/procurement")
        if mgmt:
            await notify(mgmt["user_id"], "procurement_new",
                         f"Procurement request · {doc['subject']} · {proj.get('name','')} — "
                         f"admin approved (your review is optional)", "/procurement")
    return {"ok": True, "status": new_status}


@api.post("/procurement/{request_id}/mgmt-action")
async def mgmt_action_procurement(request_id: str, payload: MgmtAction,
                                   user: User = Depends(require_roles("management"))):
    _mgmt_gate(user, "procurement")
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if user.project_id and doc["project_id"] != user.project_id:
        raise HTTPException(403, "Project not in your scope")
    # Management review is OPTIONAL and PARALLEL — it records an endorsement/comment
    # but never changes the workflow status (it does not gate the flow to Accounts).
    if doc["status"] in ("rejected", "cancelled"):
        raise HTTPException(400, f"Cannot review a {doc['status']} request")
    if payload.action != "approve" and not payload.note.strip():
        raise HTTPException(400, "A note is required for reject / clarification")
    await db.procurement.update_one(
        {"request_id": request_id},
        {"$set": {"mgmt_decision": payload.action,
                  "mgmt_action_by": user.user_id,
                  "mgmt_action_at": now(),
                  "mgmt_note": payload.note}})
    msg = f"Procurement '{doc['subject']}' — management {payload.action}"
    if payload.note:
        msg += f" · {payload.note}"
    await notify(doc["requested_by"], f"procurement_mgmt_{payload.action}", msg, "/procurement")
    await notify_role("admin", f"procurement_mgmt_{payload.action}", msg, "/procurement")
    return {"ok": True, "status": doc["status"], "mgmt_decision": payload.action}


@api.post("/procurement/{request_id}/cancel")
async def cancel_procurement(request_id: str, payload: ProcCancel,
                              user: User = Depends(require_roles("admin"))):
    """Admin cancels a procurement request raised in error; reason kept on record."""
    doc = await db.procurement.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Request not found")
    if doc["status"] == "cancelled":
        raise HTTPException(400, "Request is already cancelled")
    if not payload.reason.strip():
        raise HTTPException(400, "A reason is required to cancel")
    await db.procurement.update_one(
        {"request_id": request_id},
        {"$set": {"status": "cancelled",
                  "cancel_reason": payload.reason.strip(),
                  "cancelled_by": user.user_id,
                  "cancelled_by_name": user.name,
                  "cancelled_at": now()}})
    msg = f"Procurement '{doc['subject']}' cancelled by admin · {payload.reason.strip()}"
    await notify(doc["requested_by"], "procurement_cancelled", msg, "/procurement")
    await notify_role("accounts", "procurement_cancelled", msg, "/procurement")
    return {"ok": True, "status": "cancelled"}


# ----- inventory (site_manager) ------------------------------------------
@api.get("/inventory")
async def list_inventory(project_id: Optional[str] = None,
                          user: User = Depends(get_current_user)):
    q: dict = {}
    if project_id:
        q["project_id"] = project_id
    if user.role in ("site_manager", "management") and user.project_id:
        q["project_id"] = user.project_id
    if user.role == "management":
        _mgmt_gate(user, "inventory")
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


async def _projects_overview(only_project: Optional[str] = None):
    q = {"project_id": only_project} if only_project else {}
    projects = await db.projects.find(q, {"_id": 0}).sort("created_at", 1).to_list(50)
    out = []
    con = {"projects": len(projects), "total_units": 0, "available": 0, "sold": 0,
           "booked_value": 0.0, "received_total": 0.0, "pending_total": 0.0}
    for p in projects:
        pid = p["project_id"]
        units = await db.units.find(
            {"project_id": pid},
            {"_id": 0, "status": 1, "total": 1, "data": 1, "final_price": 1, "vault": 1}).to_list(5000)
        sold = [u for u in units if u.get("status") == "sold"]
        _charge_keys = [c["key"] for c in (p.get("columns") or []) if c.get("tag") == "charge"]
        # Sold value = live sum of component charges over sold plots — identical to the
        # component card's Grand Total (Billed), so the two can never diverge.
        booked = round(sum(sum(_num(u.get("data", {}).get(k)) for k in _charge_keys) for u in sold), 2)
        # Vault stream: booked value + attach rate (sold plots that opted into The Vault)
        sold_with_vault = [u for u in sold if (u.get("vault") or {}).get("enabled")]
        vault_booked = round(sum(_num((u.get("vault") or {}).get("total")) for u in sold_with_vault), 2)
        has_vault = bool((p.get("vault_config") or {}).get("enabled")) or len(sold_with_vault) > 0
        # received split by stream (verified receipts drive paid_amount)
        land_received = vault_received = 0.0
        async for _p in db.payments.find({"project_id": pid}, {"_id": 0, "paid_amount": 1, "stream": 1}):
            if (_p.get("stream") or "land") == "vault":
                vault_received += _num(_p.get("paid_amount"))
            else:
                land_received += _num(_p.get("paid_amount"))
        land_received = round(land_received, 2)
        vault_received = round(vault_received, 2)
        received = round(await _sum_field(db.payments, {"project_id": pid}, "paid_amount"), 2)
        retained = round(await _sum_field(db.cancellations, {"project_id": pid}, "balance_retained"), 2)
        received = round(received + retained, 2)
        awaiting = 0.0
        async for _p in db.payments.find({"project_id": pid}, {"_id": 0, "receipts": 1}):
            awaiting += sum(_num(r.get("amount")) for r in _p.get("receipts", [])
                            if r.get("verification_status") == "pending")
        awaiting = round(awaiting, 2)
        pending = round(max(0.0, booked - received), 2)
        # verified-received bifurcation per component (only explicit receipt allocations)
        received_by_key: dict = {}
        async for _pp in db.payments.find({"project_id": pid}, {"_id": 0, "receipts": 1}):
            for r in _pp.get("receipts", []):
                if r.get("verification_status") == "verified":
                    for a in r.get("allocations", []):
                        k = a.get("key", "")
                        received_by_key[k] = received_by_key.get(k, 0.0) + _num(a.get("amount"))
        pivots = []
        for c in (p.get("columns") or []):
            if c["tag"] != "charge":
                continue
            k = c["key"]
            pivots.append({
                "key": k, "label": c["label"], "tag": "charge",
                "billed": round(sum(_num(u.get("data", {}).get(k)) for u in sold), 2),
                "received": round(received_by_key.get(k, 0.0), 2),
            })
        # grand total row = exact sum of the component rows above (never a stored total)
        pivots.append({
            "key": "__grand_total__", "label": "Grand Total", "tag": "total",
            "billed": round(sum(pv["billed"] for pv in pivots), 2),
            "received": round(sum(pv["received"] for pv in pivots), 2),
        })
        out.append({
            "project_id": pid, "name": p["name"], "kind": p.get("kind", ""),
            "columns": p.get("columns", []),
            "total_units": len(units), "available": len(units) - len(sold), "sold": len(sold),
            "booked_value": booked, "received_total": received, "pending_total": pending,
            "awaiting_verification": awaiting,
            "pivots": pivots,
            "has_vault": has_vault,
            "streams": {
                "land": {"billed": booked, "received": land_received,
                         "pending": round(max(0.0, booked - land_received), 2)},
                "vault": {"billed": vault_booked, "received": vault_received,
                          "pending": round(max(0.0, vault_booked - vault_received), 2),
                          "attach_count": len(sold_with_vault)},
            },
        })
        con["total_units"] += len(units); con["available"] += len(units) - len(sold)
        con["sold"] += len(sold); con["booked_value"] += booked
        con["received_total"] += received; con["pending_total"] += pending
        con["vault_booked"] = round(con.get("vault_booked", 0.0) + vault_booked, 2)
        con["vault_received"] = round(con.get("vault_received", 0.0) + vault_received, 2)
        con["land_booked"] = round(con.get("land_booked", 0.0) + booked, 2)
        con["land_received"] = round(con.get("land_received", 0.0) + land_received, 2)
        con["vault_attach"] = con.get("vault_attach", 0) + len(sold_with_vault)
    for k in ("booked_value", "received_total", "pending_total"):
        con[k] = round(con[k], 2)
    return out, con


@api.post("/projects/{project_id}/recompute-totals")
async def recompute_totals(project_id: str, dry_run: bool = False,
                            user: User = Depends(require_roles("admin", "post_sales"))):
    """Re-sum every plot's charge components and update the stored Grand Total (and the
    total-tagged column) so a hand-typed total can never drift from its components.
    With dry_run=true, computes the before/after list WITHOUT writing anything."""
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    cols = proj.get("columns") or []
    charge_keys = [c["key"] for c in cols if c.get("tag") == "charge"]
    total_cols = [c for c in cols if c.get("tag") == "total"]
    total_key = total_cols[0]["key"] if total_cols else None
    units = await db.units.find({"project_id": project_id}, {"_id": 0}).to_list(5000)
    updated, changed = 0, []
    for u in units:
        data = dict(u.get("data", {}) or {})
        new_total = round(sum(_num(data.get(k)) for k in charge_keys), 2)
        old_total = round(_num(u.get("total")), 2)
        if not dry_run:
            if total_key:
                data[total_key] = new_total
            await db.units.update_one({"unit_id": u["unit_id"]},
                                      {"$set": {"total": new_total, "data": data}})
        updated += 1
        if abs(new_total - old_total) > 0.001:
            changed.append({"plot_number": u.get("plot_number"),
                            "old": old_total, "new": new_total,
                            "delta": round(new_total - old_total, 2)})
    return {"ok": True, "dry_run": dry_run, "updated": updated, "changed": len(changed),
            "changed_details": sorted(changed, key=lambda x: str(x["plot_number"]))[:500]}


def _add_months(d, months: int):
    import calendar
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)


async def _collections_data(user: User, months: int) -> dict:
    if months not in (1, 3, 6, 12):
        months = 1
    start = datetime.now(timezone.utc).date()
    end = _add_months(start, months)
    start_s, end_s = start.isoformat(), end.isoformat()
    proj_q: dict = {}
    if user.role in ("site_manager", "management") and user.project_id:
        proj_q = {"project_id": user.project_id}
    pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
        proj_q or {}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
    sold = {u["unit_id"]: u for u in await db.units.find(
        {**proj_q, "status": "sold"},
        {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1, "project_id": 1}).to_list(8000)}
    agg: dict = {}
    window_items, overdue_items = [], []
    overdue_total = 0.0
    async for p in db.payments.find(proj_q, {"_id": 0}):
        due = p.get("due_date") or ""
        if not (len(due) == 10):
            continue
        exp = round(_num(p.get("amount")), 2)
        collected = round(sum(_num(r.get("amount")) for r in p.get("receipts", [])
                              if r.get("verification_status") == "verified"), 2)
        balance = round(exp - collected, 2)
        u = sold.get(p.get("unit_id"), {})
        pid = p.get("project_id")
        row = {"project_id": pid, "project": pnames.get(pid, "\u2014"),
               "plot_number": u.get("plot_number", "?"), "buyer_name": u.get("buyer_name") or "",
               "instalment": p.get("notes") or f"#{p.get('seq')}", "due_date": due,
               "expected": exp, "received": collected, "outstanding": balance}
        if start_s <= due <= end_s:
            a = agg.setdefault(pid, {"expected": 0.0, "collected": 0.0})
            a["expected"] += exp
            a["collected"] += collected
            window_items.append(row)
        if due < start_s and balance > 0.01:
            days = (start - datetime.fromisoformat(due).date()).days
            overdue_total += balance
            overdue_items.append({**row, "days_overdue": days})
    by_project, tot_exp, tot_col = [], 0.0, 0.0
    for pid, a in agg.items():
        exp = round(a["expected"], 2); col = round(a["collected"], 2)
        tot_exp += exp; tot_col += col
        by_project.append({"project_id": pid, "name": pnames.get(pid, "\u2014"),
                           "expected": exp, "collected": col, "outstanding": round(exp - col, 2)})
    by_project.sort(key=lambda x: -x["expected"])
    window_items.sort(key=lambda x: x["due_date"])
    overdue_items.sort(key=lambda x: -x["days_overdue"])
    return {"months": months, "start": start_s, "end": end_s,
            "expected": round(tot_exp, 2), "collected": round(tot_col, 2),
            "outstanding": round(tot_exp - tot_col, 2), "by_project": by_project,
            "overdue": {"total": round(overdue_total, 2), "count": len(overdue_items),
                        "items": overdue_items[:50]},
            "items": window_items}


@api.get("/dashboard/collections")
async def dashboard_collections(months: int = 1, user: User = Depends(get_current_user)):
    """Expected (instalments due) vs Received for a forward window, plus overdue alerts."""
    d = await _collections_data(user, months)
    d.pop("items", None)   # detail rows only exposed via CSV
    return d


@api.get("/dashboard/collections.csv")
async def dashboard_collections_csv(months: int = 1,
                                     user: User = Depends(require_roles("admin", "accounts"))):
    d = await _collections_data(user, months)
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow([f"Collections Outlook  {d['start']} to {d['end']}  ({d['months']} month window)"])
    w.writerow([])
    w.writerow(["Project", "Plot", "Buyer", "Instalment", "Due Date", "Expected", "Received", "Outstanding"])
    for r in d["items"]:
        w.writerow([r["project"], r["plot_number"], r["buyer_name"], r["instalment"],
                    r["due_date"], r["expected"], r["received"], r["outstanding"]])
    w.writerow([])
    w.writerow(["TOTAL", "", "", "", "", d["expected"], d["collected"], d["outstanding"]])
    if d["overdue"]["count"]:
        w.writerow([])
        w.writerow([f"OVERDUE (past due, unpaid)  count {d['overdue']['count']}  total {d['overdue']['total']}"])
        w.writerow(["Project", "Plot", "Buyer", "Instalment", "Due Date", "Days Overdue", "Outstanding"])
        for r in d["overdue"]["items"]:
            w.writerow([r["project"], r["plot_number"], r["buyer_name"], r["instalment"],
                        r["due_date"], r["days_overdue"], r["outstanding"]])
    csv_bytes = buf.getvalue().encode("utf-8")
    fn = f"Collections_{d['start']}_to_{d['end']}.csv"
    return Response(content=csv_bytes, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@api.get("/needs-bifurcation")
async def needs_bifurcation(project_id: Optional[str] = None,
                             user: User = Depends(require_roles("admin", "accounts", "post_sales"))):
    """Sold plots that have verified money not yet split by component, so Post-Sales
    knows exactly what to bifurcate. Sorted by the unbifurcated amount, largest first."""
    q = {"project_id": project_id} if project_id else {}
    pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
        {} if not project_id else q, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
    units = {u["unit_id"]: u for u in await db.units.find(
        {**q, "status": "sold"}, {"_id": 0, "unit_id": 1, "plot_number": 1,
                                   "buyer_name": 1, "project_id": 1}).to_list(8000)}
    by_unit: dict = {}
    async for pay in db.payments.find(q, {"_id": 0, "unit_id": 1, "receipts": 1}):
        uid = pay.get("unit_id")
        for r in pay.get("receipts", []):
            if r.get("verification_status") != "verified":
                continue
            amt = round(_num(r.get("amount")), 2)
            has_alloc = bool(r.get("allocations"))
            a = by_unit.setdefault(uid, {"verified": 0.0, "unbifurcated": 0.0, "count": 0})
            a["verified"] += amt
            if not has_alloc:
                a["unbifurcated"] += amt
                a["count"] += 1
    items, grand = [], 0.0
    for uid, a in by_unit.items():
        unb = round(a["unbifurcated"], 2)
        if unb <= 0.01:
            continue
        u = units.get(uid, {})
        grand += unb
        items.append({"unit_id": uid, "plot_number": u.get("plot_number", "?"),
                      "buyer_name": u.get("buyer_name") or "",
                      "project_id": u.get("project_id"), "project": pnames.get(u.get("project_id"), "\u2014"),
                      "verified": round(a["verified"], 2), "unbifurcated": unb,
                      "receipts": a["count"]})
    items.sort(key=lambda x: -x["unbifurcated"])
    return {"total": round(grand, 2), "count": len(items), "items": items}


@api.get("/bifurcation-progress")
async def bifurcation_progress(project_id: Optional[str] = None,
                               user: User = Depends(require_roles("admin", "accounts", "post_sales", "management"))):
    """Per-project reconciliation progress: what share of VERIFIED money has been split
    by component (bifurcated) vs still unallocated. Lets reps see what's left to reconcile."""
    q = {"project_id": project_id} if project_id else {}
    pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
        {} if not project_id else q, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
    per: dict = {}
    async for pay in db.payments.find(q, {"_id": 0, "project_id": 1, "receipts": 1}):
        pid = pay.get("project_id")
        for r in pay.get("receipts", []):
            if r.get("verification_status") != "verified":
                continue
            amt = round(_num(r.get("amount")), 2)
            a = per.setdefault(pid, {"verified": 0.0, "bifurcated": 0.0, "pending": 0})
            a["verified"] += amt
            if r.get("allocations"):
                a["bifurcated"] += amt
            else:
                a["pending"] += 1
    items = []
    for pid, a in per.items():
        v = round(a["verified"], 2)
        if v <= 0.01:
            continue
        b = round(a["bifurcated"], 2)
        items.append({"project_id": pid, "project": pnames.get(pid, "\u2014"),
                      "verified": v, "bifurcated": b, "unbifurcated": round(v - b, 2),
                      "pending_receipts": a["pending"],
                      "pct": round(b / v * 100, 1) if v > 0 else 0.0})
    items.sort(key=lambda x: x["pct"])  # least reconciled first
    tv = round(sum(i["verified"] for i in items), 2)
    tb = round(sum(i["bifurcated"] for i in items), 2)
    return {"items": items, "verified": tv, "bifurcated": tb,
            "unbifurcated": round(tv - tb, 2),
            "pct": round(tb / tv * 100, 1) if tv > 0 else 0.0}



@api.get("/activity")
async def activity_feed(project_id: Optional[str] = None, limit: int = 120,
                        user: User = Depends(require_roles("admin"))):
    """Unified project-wide timeline: sales/bookings, schedule edits, receipt actions."""
    q = {"project_id": project_id} if project_id else {}
    pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
        {} if not project_id else {"project_id": project_id},
        {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
    units = {u["unit_id"]: u for u in await db.units.find(
        q or {}, {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1}).to_list(8000)}
    events = []
    async for l in db.schedule_logs.find(q, {"_id": 0}):
        created = l.get("action") == "created"
        events.append({
            "at": l.get("at"), "type": "sale" if created else "schedule",
            "actor": l.get("by_name"), "role": l.get("by_role"),
            "plot_number": l.get("plot_number"), "project": pnames.get(l.get("project_id"), "\u2014"),
            "detail": (f"Sale booked · {l.get('count_after')} instalment(s) · \u20B9{l.get('total_after', 0):,.0f}"
                       if created else
                       f"Schedule edited · {l.get('count_before')}\u2192{l.get('count_after')} instalment(s) · \u20B9{l.get('total_before', 0):,.0f}\u2192\u20B9{l.get('total_after', 0):,.0f}"),
        })
    labels = {"submitted": "Receipt recorded", "verified": "Receipt verified",
              "returned": "Receipt returned", "resubmitted": "Receipt corrected",
              "bifurcated": "Receipt bifurcated", "auto_bifurcated": "Receipt auto-bifurcated"}
    async for pay in db.payments.find(q, {"_id": 0}):
        u = units.get(pay.get("unit_id"), {})
        for r in pay.get("receipts", []):
            amt = round(_num(r.get("amount")), 2)
            for h in r.get("history", []):
                events.append({
                    "at": h.get("at"), "type": "receipt", "subtype": h.get("action"),
                    "actor": h.get("by_name"), "plot_number": u.get("plot_number", "?"),
                    "project": pnames.get(pay.get("project_id"), "\u2014"),
                    "detail": f"{labels.get(h.get('action'), h.get('action'))} · \u20B9{amt:,.0f}"
                              + (f" · {h.get('reason')}" if h.get("reason") else ""),
                })
    events = [e for e in events if e.get("at")]
    events.sort(key=lambda x: x["at"], reverse=True)
    return events[:limit]


@api.get("/dashboard")
async def dashboard(user: User = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date().isoformat()
    proj_q: dict = {}
    if user.role in ("site_manager", "management") and user.project_id:
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
        # compact Collections widget data (§7/§34): one row per schedule installment of sold plots
        sold_units = {u["unit_id"]: u for u in await db.units.find(
            {"status": "sold"}, {"_id": 0, "unit_id": 1, "plot_number": 1, "buyer_name": 1, "project_id": 1}).to_list(5000)}
        pnames = {p["project_id"]: p["name"] for p in await db.projects.find(
            {}, {"_id": 0, "project_id": 1, "name": 1}).to_list(50)}
        collections = []
        async for p in db.payments.find({}, {"_id": 0}):
            u = sold_units.get(p["unit_id"])
            if not u:
                continue
            receipts = p.get("receipts", [])
            received = round(sum(_num(r.get("amount")) for r in receipts if r.get("verification_status") == "verified"), 2)
            awaiting = round(sum(_num(r.get("amount")) for r in receipts if r.get("verification_status") == "pending"), 2)
            returned = any(r.get("verification_status") == "returned" for r in receipts)
            exp = round(_num(p.get("amount")), 2)
            due = p.get("due_date")
            if returned:
                verification = "returned"
            elif awaiting > 0:
                verification = "awaiting"
            elif received >= exp - 0.01 and exp > 0:
                verification = "verified"
            else:
                verification = "none"
            if p.get("status") == "received":
                coll_status = "received"
            elif received > 0:
                coll_status = "partial"
            elif due and due < today:
                coll_status = "overdue"
            elif due and due == today:
                coll_status = "due_today"
            else:
                coll_status = "upcoming"
            expected_remaining = next((r.get("expected_remaining_date") for r in receipts
                                       if r.get("expected_remaining_date") and r.get("verification_status") in ("pending", "verified")), None)
            collections.append({
                "payment_id": p.get("payment_id"), "unit_id": p["unit_id"],
                "plot_number": u.get("plot_number"), "buyer_name": u.get("buyer_name") or "—",
                "project_name": pnames.get(u.get("project_id"), ""),
                "installment": p.get("notes") or f"Instalment {p.get('seq')}",
                "due_amount": exp, "due_date": due, "received": received, "awaiting": awaiting,
                "balance": round(exp - received, 2), "status": coll_status, "verification": verification,
                "expected_remaining_date": expected_remaining,
            })
        collections.sort(key=lambda c: (c["due_date"] or "z", _plot_key(c["plot_number"] or "")))
        base.update({
            "sales_booked": sales_booked,
            "my_sales_count": my_sales,
            "my_sales_value": my_value,
            "recent_sales": recent_sales,
            "collections": collections,
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
        for st in ["pending_management", "management_clarification", "pending_admin", "pending_clarification", "approved", "paid", "rejected"]:
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

    # ================= MANAGEMENT (view-only, scoped to one project) =========
    if user.role == "management":
        pid = user.project_id
        by_project, consolidated = await _projects_overview(pid)
        approvals = await db.procurement.find(
            {"project_id": pid, "status": {"$in": ["approved", "po_issued"]},
             "mgmt_action_at": None},
            {"_id": 0}).sort("requested_at", -1).limit(10).to_list(10)
        recent_sales = await db.units.find(
            {"project_id": pid, "status": "sold"}, {"_id": 0}).sort("sold_at", -1).limit(6).to_list(6)
        site_procs = await db.procurement.find(
            {"project_id": pid, "status": {"$in": ["po_issued", "paid"]}}, {"_id": 0}).to_list(500)
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
        mgmt_pending = await db.procurement.count_documents(
            {"project_id": pid, "status": {"$in": ["approved", "po_issued"]},
             "mgmt_action_at": None})
        proj = await db.projects.find_one({"project_id": pid}, {"_id": 0}) or {}
        base.update({
            "permissions": user.permissions or [],
            "project_id": pid,
            "project_name": proj.get("name", ""),
            "mgmt_approvals_pending": mgmt_pending,
            "procurement_approvals": approvals,
            "recent_sales": recent_sales,
            "site_bills": {"pending": round(site_pending, 2), "paid": round(site_paid, 2),
                           "count": len(site_procs),
                           "milestones": sorted(site_milestones, key=lambda x: (x["status"] == "paid", x.get("due") or ""))[:8]},
            "by_project": by_project,
            "consolidated": consolidated,
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



async def _migrate_receipt_verification():
    """Backfill legacy receipts (recorded under the old Accounts flow) as
    'verified' so historical confirmed money keeps counting, then recompute."""
    fixed = 0
    async for pay in db.payments.find({"receipts.0": {"$exists": True}}):
        receipts = pay.get("receipts", [])
        changed = False
        for r in receipts:
            if not r.get("verification_status"):
                r["verification_status"] = "verified"
                r.setdefault("receipt_id", new_id("rc"))
                r.setdefault("verified_by_name", "Migrated")
                r.setdefault("verified_at", r.get("at") or now())
                changed = True
        if changed:
            derived = _recompute_payment({**pay, "receipts": receipts})
            await db.payments.update_one({"_id": pay["_id"]}, {"$set": {"receipts": receipts, **derived}})
            fixed += 1
    if fixed:
        log.info("Migrated receipt verification on %d payment(s)", fixed)


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



# Canonical column tags for Central Vista Farms (self-heals any environment).
_CVF_TAGS = {
    "farm": "plot_id", "extent_sft": "area", "bsp": "charge", "guidance_value": "reference",
    "development_charge": "charge", "18_gst": "charge", "east_facing_plc": "charge",
    "corner_plc": "charge", "cv_facing_plc": "charge", "2_or_more_plcs": "charge",
    "legal_fee": "charge", "18_gst_2": "charge", "electricity_infrastructure_charges": "charge",
    "18_gst_3": "charge", "khata_registration_charges": "charge", "18_gst_4": "charge",
    "advance_maintenance_2_years": "charge", "18_gst_5": "charge", "club_membership": "charge",
    "18_gst_of_club_membership": "charge", "ifms": "charge", "sinking_fund": "charge",
    "stamp_duty": "charge", "net_payable": "total",
}
_CVF_VAULT = {
    "enabled": True,
    "variants": [
        {"variant_id": "7000", "label": "7000 sqft", "construction": 7750000, "gst": 1395000, "total": 9145000},
        {"variant_id": "8000", "label": "8000 sqft", "construction": 8400000, "gst": 1512000, "total": 9912000},
        {"variant_id": "8000_2br", "label": "8000 sqft (2 BR)", "construction": 9100000, "gst": 1638000, "total": 10738000},
        {"variant_id": "10000", "label": "10000 sqft", "construction": 11000000, "gst": 1980000, "total": 12980000},
    ],
    "schedule_template": (
        [{"label": "On Booking", "pct": 10}, {"label": "On Agreement to Sell", "pct": 10}]
        + [{"label": f"Instalment {i}", "pct": 10} for i in range(1, 8)]
        + [{"label": "On Offer of Possession", "pct": 10, "on_possession": True}]
    ),
}


async def _migrate_cvf():
    """Idempotent self-heal for Central Vista Farms. Matched by NAME so it works in any
    environment. If the CVF project is structurally broken (missing its real charge
    columns like BSP / NET PAYABLE — as happened on production), rebuild the full column
    set and heal each AVAILABLE plot's data from the embedded canonical seed
    (backend/cvf_seed.json). Always ensures The Vault config. Never touches sold plots or
    any other project (e.g. Vacation Village)."""
    proj = await db.projects.find_one({"name": {"$regex": "^Central Vista", "$options": "i"}}, {"_id": 0})
    if not proj:
        return
    pid = proj["project_id"]
    cols = proj.get("columns") or []
    keys = {c.get("key") for c in cols}
    broken = not ({"bsp", "net_payable"} <= keys)

    seed = None
    seed_path = os.path.join(os.path.dirname(__file__), "cvf_seed.json")
    if os.path.exists(seed_path):
        try:
            with open(seed_path) as f:
                seed = json.load(f)
        except Exception as e:
            log.warning("CVF seed load failed: %s", e)

    updates = {}
    if broken and seed and seed.get("columns"):
        # Rebuild the canonical column structure.
        updates["columns"] = seed["columns"]
    else:
        # Structured already — just ensure canonical tags (cheap).
        changed = False
        for c in cols:
            want = _CVF_TAGS.get(c.get("key"))
            if want and c.get("tag") != want:
                c["tag"] = want
                changed = True
        if changed:
            updates["columns"] = cols
    if not (proj.get("vault_config") or {}).get("enabled"):
        updates["vault_config"] = seed.get("vault_config") if (seed and seed.get("vault_config")) else _CVF_VAULT
    if updates:
        await db.projects.update_one({"project_id": pid}, {"$set": updates})
        log.info("CVF project healed: %s", ", ".join(updates.keys()))

    # Heal plot data only when the project was broken (one-time), so booked/edited data
    # is never overwritten on subsequent boots.
    if broken and seed and seed.get("units"):
        existing = await db.units.find({"project_id": pid}, {"_id": 0, "unit_id": 1, "plot_number": 1, "status": 1}).to_list(5000)
        by_pn = {str(u["plot_number"]): u for u in existing}
        healed = added = 0
        for su in seed["units"]:
            pn = str(su["plot_number"])
            cur = by_pn.get(pn)
            if cur is None:
                await db.units.insert_one({
                    "unit_id": "unit_" + uuid.uuid4().hex[:12], "project_id": pid,
                    "plot_number": pn, "area_sqft": su.get("area_sqft", 0), "area": su.get("area_sqft", 0),
                    "plc_details": "", "other_charges": 0, "status": "available",
                    "data": su.get("data", {}), "total": su.get("total", 0),
                    "created_at": now()})
                added += 1
            elif cur.get("status") != "sold":
                await db.units.update_one({"unit_id": cur["unit_id"]}, {"$set": {
                    "area_sqft": su.get("area_sqft", 0), "data": su.get("data", {}),
                    "total": su.get("total", 0)}})
                healed += 1
        log.info("CVF plots healed=%d added=%d (available only; sold untouched)", healed, added)


@app.on_event("startup")
async def startup():
    await db.users.create_index("phone", unique=True)
    await db.units.create_index("unit_id")
    await db.units.create_index([("project_id", 1), ("plot_number", 1)])
    await _scrub_nonfinite_data()
    await _migrate_receipt_verification()
    await _migrate_cvf()
    # Management no longer gates procurement — advance any requests parked at the
    # old Management stage straight to Accounts-ready (admin already approved them).
    r = await db.procurement.update_many(
        {"status": {"$in": ["pending_management", "management_clarification"]}},
        {"$set": {"status": "approved"}})
    if r.modified_count:
        log.info("Advanced %d procurement request(s) past the retired Management gate", r.modified_count)
    # NOTE: object storage is NOT initialised here — files now live in MongoDB (GridFS).
    # The legacy object-storage proxy is only touched lazily when an OLD file is
    # downloaded, so a broken/unreachable proxy can never block app startup.
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
