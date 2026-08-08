# Agrocorp Lite — PRD

## Team (4 roles)
- 1 Admin
- 1 Accounts
- 1 Post-Sales Rep
- 2 Site Managers (one per project)

## Sales flow (Post-Sales → Accounts + Admin)
1. Post-Sales picks an available plot
2. Enters buyer name, buyer contact, sale date, final price (all-inclusive, negotiated), booking amount
3. Enters payment schedule table: row-per-installment `{due_date, amount, notes}`
4. Schedule total MUST equal (final_price − booking_amount)
5. On submit: unit becomes `sold`, N payment rows created, Admin + Accounts notified (in-app)
6. Accounts opens Sales & Payments page → on each due date, marks the row `received` (with received_date + notes) or leaves `pending`

## Procurement flow (Site Manager → Admin → Accounts)
1. Site Manager raises: subject, item list (name, quantity, unit, est_cost, notes), priority (low/medium/high/urgent), notes
2. Admin gets in-app notification
3. Admin decides: **approve** / **reject** / **need clarification** (with admin note)
4. If needs clarification → status stays open, site manager sees the note; can update the request via a fresh submission
5. If approved → Accounts gets notified
6. Accounts records PO number, paid amount, paid date → status = `paid`

## Inventory flow (Site Manager only)
- Free-form CRUD: `{name, quantity, unit, notes}`
- No auto-decrement from procurement (kept simple)

## Admin setup flow
1. Admin logs in (initial password = phone number, forced reset)
2. Adds contacts (users) — initial password for each user is their phone
3. Creates projects, assigns a site manager to each
4. Uploads inventory Excel per project (same VV RERA cost sheet format we've been using)

## Auth
- **Phone-as-password on first login** — no email flows anywhere
- Forced reset on first login (`must_reset_password: true`)
- If a user forgets password → admin clicks "Reset password" → password goes back to their phone number
- JWT bearer tokens, 12-hour TTL, bcrypt hashes

## Data model highlights
- **`users`**: `{user_id, name, phone (unique), email?, role, project_id?, is_active, must_reset_password}`
- **`projects`**: `{project_id, name, location, site_manager_id?}`
- **`units`**: `{unit_id, project_id, plot_number, area_sqft, plc_details, other_charges, status: available|sold, buyer_name, buyer_contact, sale_date, final_price, booking_amount}`
- **`payments`**: `{payment_id, unit_id, project_id, seq, due_date, amount, status: pending|received, received_date, received_notes}`
- **`procurement`**: `{request_id, project_id, subject, items:[{name,quantity,unit,est_cost,notes}], priority, notes, status, admin_note, po_number, paid_amount, paid_date, paid_notes}`
- **`inventory`**: `{item_id, project_id, name, quantity, unit, notes, updated_by, updated_at}`
- **`notifications`**: `{notification_id, user_id, kind, message, link?, is_read}`

## Excluded from Lite (present in Agrocorp Admin, deliberately dropped)
- Cost-sheet-aware structured pricing block (BSP, PLC breakdown, OC1/OC2, IFMS math). Excel is stored as reference dicts only.
- Component-aware payment plans (post_sales enters the schedule manually every time).
- 2-step sale approval / 3-step payment verification.
- Cancellation + refund workflow.
- SMTP / cron / reminder engine / customer notifications.
- Emergent Object Storage / document vault.
- Cost Sheet Preview / printable PDF page.
- Audit log (kept in-line via `marked_by`/`updated_by` fields only).
- Multi-Wave role hierarchy — just 4 roles.

## Design principles
- Every state transition writes an in-app notification to the roles that should see it. Nothing more.
- All money is manual — no computed schedules, no automatic GST math. Post-Sales enters the exact amounts.
- All auth flows are in-house (no third-party providers).
- Backend stays single-file until domain complexity justifies routers.

## Roadmap (future waves for Lite)
- **P1:** CSV export of payments watchlist for accountant reconciliation
- **P1:** In-app comment thread on procurement requests instead of a single admin_note
- **P2:** Simple daily reminder page for accounts (no email, just an in-app "today's due" view)
- **P2:** Site manager can tie approved procurement to inventory line items (auto-append quantities)

---
## Import & Setup log (2026-08-06)
- Imported existing GitHub repo `InternalLiteApp` (Agrocorp Lite) into /app.
- Fixes applied to make it runnable:
  - Created `backend/.env` (MONGO_URL, DB_NAME=agrocorp_lite, JWT_SECRET, ADMIN_PHONE, ADMIN_EMAIL).
  - Created `frontend/.env` (REACT_APP_BACKEND_URL preview URL).
  - Installed missing python dep `et_xmlfile` (openpyxl transitive) + pinned in requirements.txt.
  - Changed ADMIN_EMAIL `.local` -> `.com` (email-validator rejects reserved `.local`).
  - Fixed Login.jsx navigate-during-render warning -> `<Navigate replace/>`.
- Verified: E2E testing agent 27/27 backend tests PASS, frontend smoke PASS.
- Admin first login: phone `9999999999` / password `9999999999` (forced reset on first login).
- DB reset to clean state after tests so first-login experience is fresh.

---
## UI Overhaul + Role Dashboards (2026-08-06)
- Applied 'Agrocorp Precision' design system: Outfit/Manrope/JetBrains Mono fonts, earthy green (#1A2F24) + clay accents, sharp 4px corners, 1px borders, fixed sidebar + glass topbar. index.css + tailwind.config.js rewritten; new shared UI kit at frontend/src/components/ui.jsx (Kpi, StatusPill, PageHeader, SectionCard, EmptyState, Modal, inr/inrCompact).
- Backend /api/dashboard is now ROLE-AWARE — returns distinct payloads per role.
- 4 role-specific dashboards under frontend/src/pages/dashboards/: Admin (Command Center), Post-Sales (Action desk), Accounts (The Ledger), Site Manager (Tactical Ops). Dispatcher in Dashboard.jsx.
- All pages restyled (Login split-screen w/ aerial bg, ResetPassword, Projects, Users, Units, Sales, Inventory, Procurement).
- Verified by testing agent: 4 role dashboards distinct + 5 regression flows pass, 0 bugs.
- Demo accounts (all past forced reset): Admin 9999999999/Repro@123, Accounts 9000000001/Accounts@123, Post-Sales 9000000002/Sales@123, Site Manager 9000000003/Site@123.

---
## Agrocorp.co.in Theme + Global Search (2026-08-06)
- Re-themed app to match www.agrocorp.co.in: Cormorant Garamond serif headings + Inter body + JetBrains Mono for numbers; olive-green palette (#5a6b10 primary, #3d4a0a dark, #7a8e1a/#8fa832 light), warm cream bg (#faf8f5), beige borders (#e8e0d0), soft green-tinted shadows, cubic-bezier(0.19,1,0.22,1) easing. Updated index.css, tailwind.config.js, ui.jsx status pills; layout unchanged per user.
- Global Search: new role-scoped backend GET /api/search (units/projects/procurement/inventory/team, min 2 chars) + GlobalSearch.jsx topbar component (debounced, ⌘K focus, arrow-key nav, grouped dropdown, click-to-navigate).
- Verified by testing agent: 11/11 search tests pass, role scoping correct, theme regression-safe, 0 bugs.

---
## Bug fix: Excel import "Header row not found" (2026-08-06)
- Root cause: importer scanned only first 10 rows and required literal 'basic sale price' in header; no CSV support; numbers with commas/₹ failed to parse.
- Fix in server.py: added _read_tabular/_read_csv (.xlsx + .csv), _detect_header (scores first 30 rows via COL_SYNS synonyms — unit/plot + area/price/charges), hardened _num (strips commas, ₹, spaces so 30,00,000 -> 3000000). Descriptive 400 with row preview if truly no header.
- Verified by testing agent: 5/5 import tests pass (varied header + title row, CSV, classic format, negative case). Test suite at backend/tests/test_units_import.py.

---
## CVF real sheet mapped (2026-08-06)
- Imported real 'CVF Inventory 24.07.26.xlsx' into Central Vista Farms (proj_01d7e89ba838): 47 units.
- Extended importer for CVF header wording: FARM# -> unit_no, NET PAYABLE -> grand total; new columns cv_facing, multi_plc (2 or more PLCs), guidance_value, electricity_infra, khata_registration, sinking_fund, stamp_duty; reordered infra synonyms so DEVELOPMENT CHARGE -> infra_dev and ELECTRICITY INFRASTRUCTURE -> electricity_infra.
- Verified: FARM# 32 -> area 7911.5, bsp 5933625, sheet_grand_total 8079622.43, multi_plc 445021.875. Testing agent 7/7 pass, no regression. Suite: backend/tests/test_cvf_import.py.

---
## Multi-project redesign — PHASE 1 (2026-08-08)
Confirmed choices: tags {plot_id,area,charge,total,reference,ignore}; rebuild from new uploads; free-form sale schedule (instalment name + due-date/On-Offer-of-Possession, partial payments, no strict total check); procurement PI/PO = file uploads (P3); phased delivery.

Delivered P1:
- Dynamic per-project inventory schema: Project.columns=[{key,label,tag}], Unit.data{}/area/total (plc_details/other_charges removed). Legacy /units/import replaced by POST /units/preview (detect columns + suggest tags) + POST /units/commit (project_id,file,mapping) which saves the project's column structure and upserts plots (rounds to 2dp, skips sold).
- Admin add plot POST /projects/{id}/plots and edit PATCH /units/{unit_id}; numeric ascending sort of plots; Project.kind field.
- Dashboards return by_project[] (pivot = sum of each charge/total/reference column across all + sold plots) + consolidated. Admin/Post-Sales/Accounts dashboards now TWO-COLUMN per project (no project selector) + consolidated strip.
- Units page: per-project sections, upload wizard (preview→map→commit), add/edit plot, dynamic horizontally-scrollable tables.
- Sell schedule: instalment name + due date OR "On Offer of Possession"; Sales page shows instalment name column. Money everywhere 2 decimals. /team→/users alias + catch-all route.
- CVF (proj_01d7e89ba838) committed via new flow (24 cols, 47 plots). VV (proj_53fb360c1f0a) has no schema yet (awaiting upload).
- Verified by testing agent: 9/9 backend + all frontend flows, 0 bugs. Suite: backend/tests/test_phase1.py. (Obsolete: test_units_import.py/test_cvf_import.py target removed endpoint.)

REMAINING:
- P2: Accounts rework — pending grouped into Plots vs Site, per-plot drilldown, partial payments (paid_amount vs amount + receipts), instalment names.
- P3: Procurement — site manager PI file upload → admin approve → accounts generate PO (file) → site manager views PO → accounts records milestone payment structure → on admin dashboard. (Needs object storage integration.)
- Go-live: preview & production use separate DBs; user uploads inventory in the LIVE app after redeploy. Raw PowerShell against prod DB is not the supported path — confirm method with support at go-live.

---
## PHASE 2 — Accounts rework (2026-08-08)
- Payment model: +paid_amount, +receipts[], status now pending|partial|received.
- POST /payments/{id}/receipt: partial/full payment entry (accumulates receipts, recomputes status), notifies admin. PATCH /payments/{id} syncs paid_amount.
- GET /accounts/overview: dues grouped into PLOTS (per project → per plot: billed/paid/pending/next_due/installments) and SITE (procurement approved/paid). list_payments supports unit_id filter.
- sell_unit: removed strict schedule==net-payable check (fully manual, per user).
- Sales page rebuilt: Plots/Site head tabs, per-project plot tables, per-plot drilldown modal (all instalments), ReceiptDialog partial-payment entry (Full balance/50% quick-fills, previous receipts). StatusPill supports 'partial'.
- Verified by testing agent: 4/4 backend + UI flows, 0 bugs. Suite: backend/tests/test_phase2.py. DB reverted clean (0 sold, 0 payments).
- Note: plot row "Billed" = sum of scheduled instalments (may be < final_price when booking paid upfront) — intended.

REMAINING: P3 procurement (PI upload → admin approve → accounts PO file → site manager views PO → accounts milestone payment structure → admin dashboard). Needs object storage.

---
## PHASE 3 — Procurement with file uploads + milestones (2026-08-08)
- Emergent object storage integrated (init_storage/put_object/get_object/save_upload; APP_NAME=agrocorp-lite; EMERGENT_LLM_KEY added to backend/.env; files collection). init on startup.
- Flow: site manager POST /procurement (multipart + PI file) -> admin /action approve -> accounts POST /procurement/{id}/po (multipart PO file + po_number, status po_issued) -> POST /procurement/{id}/milestones (structure) -> POST /procurement/{id}/milestones/{idx}/pay (mark paid; all paid => status paid). GET /files/{file_id}/download?token=JWT (401/404 guarded). Old /payment endpoint removed.
- accounts_overview Site head + admin dashboard site_bills now driven by PO milestones. StatusPill: po_issued label.
- Frontend Procurement.jsx: PI upload in new request, PI/PO download links, Issue-PO dialog (PO upload), Milestone dialog (set structure + mark paid, stays open). lib/api fileUrl().
- Verified by testing agent: 16/16 backend + all UI, 0 functional bugs. Suite backend/tests/test_phase3.py. DB cleaned (0 procurement/files/payments/sold) — pre-launch.

ALL THREE PHASES COMPLETE. Go-live: redeploy to push code; production has its OWN DB, so upload both projects' inventory in the LIVE app after redeploy. Raw PowerShell against prod DB is not supported — use the live app UI / contact support for any prod data ops.
