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

---
## HOTFIX — Inventory upload Cloudflare 520 on production (2026-08-08)
- Symptom: uploading Vacation Village inventory (256 plots) on PRODUCTION errored with Cloudflare 520 "origin returned an empty response". CVF (47 plots) worked.
- Root cause: /units/commit did 2 sequential DB round-trips per row (find_one + update_one/insert_one) = ~512 awaited calls. On production's remote MongoDB (higher latency) this exceeded the worker/proxy timeout, worker was killed → empty response → CF 520. Preview's local Mongo was fast so it never showed.
- Fix (backend/server.py commit_units): one find() to load existing plots into a map, build pymongo UpdateOne/InsertOne ops, single bulk_write(ordered=False). Added startup indexes: units.unit_id and units.(project_id,plot_number).
- Verified in preview via curl: CVF commit = 47 updated, 0 errors in 0.16s (single bulk_write). Perf on prod can only be confirmed after REDEPLOY.
- ACTION FOR USER: Redeploy, then retry Vacation Village upload on the live app.

---
## HOTFIX 2 — REAL root cause of VV upload 520 (2026-08-08)
- File "VV CKM RERA Area Inventory": openpyxl reported dims A1:HP14654 (14,654 rows x 224 cols) though only 256 real plots. Old _read_tabular did `[list(r) for r in ws.iter_rows()]` = materialised ~3.28M cells into memory (6.3s read + big RAM) -> on memory-limited prod container the worker was OOM-killed -> empty response -> Cloudflare 520. Happened on BOTH preview & commit; HOTFIX 1 (bulk_write) alone didn't fix it.
- Fix (_read_tabular): open read_only=True, stream rows, stop after 25 consecutive blank rows, trim trailing all-empty (phantom) columns. Result: 0.03s read, 16 cols, 259 rows.
- Verified via curl with the ACTUAL file against preview: /units/preview = 16 cols/256 rows in 0.25s; /units/commit = 256 updated, 0 errors in 0.25s. VV project (proj_53fb360c1f0a) now has 16-col dynamic schema + 256 units populated.
- ACTION FOR USER: REDEPLOY again (this fix wasn't in the last deploy), then upload VV on live app.

---
## PHASE 4 — Admin UI/logic edits (2026-08-10)
- Sell form: buyer_name/buyer_contact now OPTIONAL (SellUnitRequest defaults ''); notification skips name when blank.
- Admin Dashboard: removed 'Consolidated · All Projects' card (kept KPI stat row); ProjectPivot table now shows only 'Sold (booked)' (removed 'All plots' column).
- Project model: +rate_per_sqft (float, ge=0). New PATCH /projects/{id}/rate (RateUpdate). GET /projects returns it.
- Projects.jsx: rebuilt into two project CARDS — editable 'Sale rate (per sq.ft)' with Save, inventory glance (total/sold from /dashboard by_project), 'Catering to this inventory' listing Admin + Process Admin (post_sales) users.
- Units.jsx: 2-column layout (grid xl:grid-cols-2), COMPACT table = Plot no + Extent(sq.ft) + Applicable PLCs (PLC = charge col whose label matches /plc/i, shown as chips only when value>0; '—' otherwise). VV has PLCs; CVF has none (shows '—').
- Sell form renamed: 'Payment breakdown' heading, 'Add breakdown' button, 'Breakdown item' col, 'Breakdown total' footer (manual empty rows kept).
- Verified: testing agent iteration_9.json — 6/6 backend + all 5 frontend edits, 0 bugs. Negative rate rejected (422). DB kept pre-launch clean (0 sold/0 payments). Rates set: CVF 2500, VV 3200.
- ACTION FOR USER: Redeploy to push these to production.

---
## HOTFIX 3 — Cloudflare 520 after login on production (2026-08-10)
- Symptom: after login on production, CF 520 "origin returned empty/malformed response". Identical code = 200 in preview.
- Root cause: NaN/Infinity float values in stored unit data (Excel error cells parsed by openpyxl data_only pass through _num unchanged). Starlette JSONResponse renders with allow_nan=False, so serializing a NaN raises mid-response → empty/invalid origin response → CF 520. Preview data happened to be clean. Reproduced in preview: injecting float('nan') into a unit.total made GET /api/units return 500 (→520 via CF).
- Fix (backend/server.py):
  1. SafeJSONResponse(JSONResponse) with recursive _sanitize_nonfinite() (NaN/Inf → null); set as FastAPI default_response_class → ALL endpoints now serialize safely even with pre-existing bad data.
  2. _num() hardened: non-finite → 0.0 (prevents storing NaN/Inf on future imports).
- Verified in preview: with NaN still in DB, GET /api/units returns 200 and the field renders as null. After cleanup, 0 non-finite values remain; dashboard/projects/units/notifications/accounts/procurement all 200.
- NOTE: could not read production runtime logs (deployment_agent only does static analysis) — root cause confirmed by reproducing the exact mechanism in preview.
- ACTION FOR USER: Redeploy to push this fix to production; the 520 after login will be resolved.

---
## PHASE 5 — Dashboard money cards + Book-plot form redesign (2026-08-10)
- Admin Dashboard project cards: the 3 mini stats are now Total Sold / Total Received / Total Pending (was Booked/Sold/Pending).
  - _projects_overview: booked = sum(final_price or total) for SOLD plots (= Grand Total). received = sum(paid_amount over all project payments, incl partials). pending = max(0, booked - received). Verified end-to-end: sale of ₹80.79L → Total Sold 80.79L, Received 0, Pending 80.79L; after a ₹30L receipt → Received 30L, Pending 50.79L.
- Book plot (Sell) form redesign (Units.jsx SellDialog, now receives project columns):
  - Title 'Book plot N'. Buyer NAME only (removed buyer contact). Sale date required. Final price prefilled = plot Grand Total (unit.total). Booking amount.
  - NEW read-only 'Payment breakdown — from plot details' table: one row per plot column (from edit form) with its value; area shown as plain number, money as ₹, grand total bold, reference italic.
  - BELOW it: the manual 'Payment schedule' table (instalment name / due date / On Offer of Possession / amount) — the prior feature, restored under this name.
- Permissions: post_sales can now EDIT plot details (edit-plot button + PATCH /units/{id} role opened to admin+post_sales). Add-plot stays admin-only.
- Verified via screenshots (dashboard labels, book form) + curl (sale/receipt/dashboard math, edit endpoint 200). NOTE: an accidental test PATCH with empty data wiped CVF plot 32 then re-imported CVF (47 updated) to restore; DB pre-launch clean (0 sold/0 payments), rates CVF 2500 / VV 3200.
- ACTION FOR USER: Redeploy to push to production.

---
## PHASE 6 — Admin cancel booking + cancellations history (2026-08-10)
- ADMIN-ONLY cancel booking. Models: CancelBookingRequest{cancel_date, amount_refunded>=0}, Cancellation{unit_id,project_id,plot_number,buyer_name,amount_paid,amount_refunded,balance_retained,cancel_date,cancelled_by,cancelled_by_name,cancelled_at}. Collection: db.cancellations.
- POST /units/{id}/cancel (admin): amount_paid = sum(payments.paid_amount for unit); balance_retained = paid - refunded; inserts Cancellation; DELETES the unit's payment schedule; reverts unit to available (unset buyer/sale fields); notifies admin+accounts.
- GET /cancellations (admin+accounts).
- Dashboard _projects_overview: received now = sum(payments.paid_amount) + sum(cancellations.balance_retained); Total Received folds in retained balance. Total Sold drops the cancelled plot (no longer sold). pending = max(0, booked - received).
- Units.jsx: sold plots show admin-only Cancel (Trash2) button → CancelDialog (fetches unit payments to show 'Amount paid so far', live Balance retained = paid - refunded, guards refund<=paid). Also edit-plot now admin+post_sales (Phase 5).
- Sales.jsx: new 'Cancellations' head tab (admin+accounts) → CancellationsView with summary (count / Total Refunded / Balance Retained) + table (Date, Plot, Buyer, Paid, Refunded, Balance retained, By).
- Verified: curl end-to-end + testing agent iteration_10.json (frontend 100%, 0 bugs). Example confirmed: paid 15L, refund 10L, retained 5L in CVF Total Received. DB left clean (sold=0, payments=0, cancellations=0).
- ACTION FOR USER: Redeploy to push to production.

---
## PHASE 7 — Dashboard sold-plots header + Total Sold match + optional due date (2026-08-10)
- AdminDashboard ProjectPivot header: replaced kind/'Project' label with '{sold}/{total} plots sold' (data-testid dash-soldplots-{project_id}).
- _projects_overview: booked (Total Sold) now = sum(u.total or final_price for sold) so it EXACTLY matches the pivot Grand Total (total-tag) Sold(booked) row.
- SellDialog.save(): due date now OPTIONAL. filled = rows with amount>0 (>=1 required); due_date = on_possession ? 'On Offer of Possession' : (r.due_date || sale_date). Removed the 'each row needs amount + due date' hard block.
- Verified: testing agent iteration_12.json — 100% (dashboard header, Total Sold==pivot Grand Total for 1 & 3 plots, no-date booking succeeds, sale-date-required + no-amount errors intact, on-possession + explicit-date regressions pass). DB left clean (sold=0/payments=0/cancellations=0).
- ACTION FOR USER: Redeploy to push to production.

---
## HOTFIX 4 — Production 520 on login (post-login data load) (2026-08-10)
- Diagnosis: direct probes to https://read-start-2.emergent.host showed the backend is UP and /api/auth/login is healthy (fast, correct 401s, no 520). So the 520 is on the post-login data load (/dashboard etc.) choking on NaN/Inf numbers in production spreadsheet data — same class as HOTFIX 3.
- Fix added: startup routine _scrub_nonfinite_data() scans db.units/db.payments/db.cancellations on boot and $sets sanitized values (NaN/Inf -> 0/null) via _has_nonfinite + _sanitize_nonfinite. Complements the existing SafeJSONResponse (response-time NaN safety). So a REDEPLOY purges bad numbers already in the production DB.
- Note: _scrub_nonfinite_data + _has_nonfinite are defined at module level ABOVE startup() (safe on cold start; Python resolves at call time anyway).
- Verified in preview: injected NaN/Inf into a unit -> restart -> startup scrubbed it (total->0, data val->null), /dashboard + /units 200. Testing agent iteration_13.json: 100% (login + all endpoints + all pages, clean startup, no regression).
- Production login note: production DB is separate; preview password 'Repro@123' does NOT work on prod (confirmed 401). User must use their production password.
- ACTION FOR USER: REDEPLOY. On deploy the scrub cleans prod data and the 520 on login/dashboard should be resolved.

---
## PHASE 8 — Full mobile responsiveness (2026-08-12)
- Layout.jsx: sidebar off-canvas on <1024px (translate-x + lg:translate-x-0) with hamburger (data-testid sidebar-open), close btn (sidebar-close), backdrop (sidebar-backdrop); auto-closes on route change; topbar left-0 lg:left-64, px-4 lg:px-8; main ml-0 lg:ml-64; content p-4 sm:p-6 lg:p-8.
- All page tables wrapped in <div class="overflow-x-auto"> (Sales, Units, Users, Procurement, Inventory, AdminDashboard, PostSalesDashboard) so wide tables scroll instead of clipping.
- 3-col money/summary grids -> grid-cols-1 sm:grid-cols-3 (stack on phones): AdminDashboard project cards, Sales summaries + CancellationsView, Accounts/PostSales dashboards.
- Sales head tabs -> flex-wrap (no horizontal overflow). Notif panel -> fixed left-3 right-3 on mobile, sm:absolute w-96 (stays in viewport).
- Verified: testing agent iteration_14.json 95% (no functional regression, desktop + mobile 390px), then the 2 flagged minor overflows (Sales tabs, notif panel) fixed and re-verified via screenshot (body scrollWidth==390, notif box x=12 w=366).
- CAUTION LEARNED: do NOT run two replace_all edits on the SAME file in one parallel batch — it caused a race that corrupted Sales.jsx tail (duplicated ReceiptDialog close + round2); fixed by removing the duplicate. Sequence same-file edits.
- DB left clean (sold/payments/cancellations/notifications = 0). ACTION FOR USER: Redeploy to push responsive UI to production.

---
## PHASE 9 — Payment maker-checker (Post Sales records → Accounts verifies) (2026-08-12)
- Reused existing payments/receipts model; extended each receipt with receipt_id, verification_status(pending|verified|returned), submitted_by/at, mode, head, allocations[], expected_remaining_date, verified_by/at, return_reason, history[].
- paid_amount is now DERIVED = sum of VERIFIED receipts (so all existing dashboard/accounts math counts only verified money, no formula rewrites). _projects_overview adds awaiting_verification (sum of pending receipt amounts).
- Endpoints: POST /payments/{id}/receipt (post_sales only, creates PENDING, validates alloc==amount & mode); POST /payments/{id}/receipts/{rid}/verify (accounts only, YES posts / NO returns w/ reason, idempotent double-verify=400); PATCH /payments/{id}/receipts/{rid} (post_sales, correct returned → pending); GET /payments/verifications?status=. accounts_overview now allows post_sales (to load Plots list).
- Maker-checker enforced in BACKEND (admin/accounts blocked from record=403; post_sales blocked from verify=403).
- Migration on startup (_migrate_receipt_verification): legacy receipts backfilled to 'verified' so historical money keeps counting.
- Frontend Sales.jsx: PlotDrilldown shows instalments+receipts w/ verification badges; ReceiptDialog enhanced (component allocation chips from plot breakdown, mode, head, expected-remaining-date, partial support); new Verification tab (accounts/admin) with pending/returned/verified filters + YES/NO. AdminDashboard project card now shows 'Awaiting Verify' mini.
- Verified: backend curl end-to-end + testing agent iteration_16.json = 100% (all 5 scenarios, guards, return/correct/resubmit). DB clean (sold=0/payments=0). Test users: post_sales 9000000001, accounts 9000000002 (Pass@123).
- NOT YET DONE (deferred, ran out of scope this pass): §35-36 downloadable plot-wise PDF Payment Report; a compact Collections widget embedded on the Post Sales *dashboard* (recording currently done via Sales & Payments > Plots).
- ACTION FOR USER: Redeploy to push to production. Production will auto-migrate old receipts to 'verified' on boot; create real post_sales & accounts users there.

---
## PHASE 10 — Management role + procurement primary-approval + rebrand (2026-06)
- NEW ROLE `management`: admin-created, scoped to exactly ONE project (project_id), with a per-user `permissions[]` checklist of sections (projects, users, units, sales, inventory, procurement). Dashboard always available. Management is VIEW-ONLY everywhere; only action allowed is procurement PRIMARY approval.
- Backend (server.py): Role literal + MGMT_SECTIONS; User.permissions + UserCreate.permissions + AccessUpdate model; require_section(section,*roles) dep + _mgmt_gate() inline gate; PATCH /users/{id}/access (admin sets permissions+project); read endpoints scoped to management project (projects/units/inventory/procurement/payments/accounts-overview) and section-gated (403 if not granted). All mutating endpoints naturally 403 for management (not in their role lists).
- Procurement flow change: on create, if a Management user is assigned to that project -> status `pending_management` and notify that manager; else -> `pending_admin` (unchanged). New POST /procurement/{id}/mgmt-action (management-only, procurement perm) approve->pending_admin / reject->rejected / clarify->management_clarification (note required for reject/clarify). Then Admin final approve (existing) -> approved -> Accounts PO. New statuses added to ProcurementRequest + mgmt_action_by/at/note fields.
- Management dashboard (ManagementDashboard.jsx): same financial pivots as Admin but scoped to assigned project, view-only, + 'awaiting your primary approval' KPI + 'Procurement · Needs Your Approval' + Site Bills.
- Frontend: App.js route section-gating; Layout NAV filtered by permissions; Users.jsx Management option + project select + permissions checklist + AccessModal (edit access); Procurement.jsx mgmt-review button + ActionDialog endpoint switch by status; Projects.jsx made resilient (optional /users fetch) + readOnly for management.
- REBRAND: app name Agrocorp Lite -> "Management Dashboard" / "Stakeholder Console" (Layout sidebar, Login, ResetPassword). Login shows company logos (/companies-logo.png) in place of old tagline; subtitle "Real-time visibility into financial, operational, sales, and project performance."; first-time text "Your password is your phone number for the first time setup"; small brand uses /agrocorp-logo.webp. AdminDashboard subtitle updated. Assets: /app/frontend/public/agrocorp-logo.webp, companies-logo.png.
- Verified: backend curl end-to-end (create mgmt+perms, section gating 403/200, procurement pending_management->mgmt approve->pending_admin->admin approve->approved, access-update) + testing agent iteration_17 (found 2 bugs) then iteration_18 = 30/30 100%. DB left clean (users=3, sold=0, payments=0, procurement=0, no management users).
- CAUTION (recurred this phase): server.py had a pre-existing duplicated/garbled tail; SOME search_replace edits silently "succeeded" but were later shadowed/lost (User.permissions, UserCreate/AccessUpdate, MgmtAction, mgmt-action endpoint, and the frontend mgmt-review button). Always GREP to confirm edits actually persisted after batch edits on a large/possibly-corrupted file.
- ACTION FOR USER: Redeploy to push to production. Then create Management users there (Team page) and assign project + sections.

---
## PHASE 11 — Plot-wise PDF Payment Report + Post Sales Collections widget (2026-06)
- Deferred payment-doc items (§35-36 report, §7/§34 collections) now DONE. Post Sales recording loop itself was already done (Phase 9).
- Backend (server.py): GET /units/{unit_id}/payment-report -> streams a reportlab-generated PDF (require_section sales/admin/accounts/post_sales). Sections: Plot Info, Payment Summary (Total Payable/Verified Received/Outstanding/Awaiting Verification/Next Due), Component Structure (charge columns vs verified allocations), Payment Plan (installments), Actual Payment History (all receipts w/ verification status), Pending Details. Company branding via /app/frontend/public/companies-logo.png. Currency uses 'Rs.' prefix in PDF (no Unicode-₹ font on server; UI keeps ₹). Helpers _plot_report_data + _build_report_pdf + _inr_plain. Added reportlab==5.0.0 to requirements.txt.
- Backend: post_sales dashboard now returns `collections` — one row per schedule installment of sold plots {plot, customer, project, installment, due_amount, due_date, received(verified), awaiting(pending), balance, status(received/partial/overdue/due_today/upcoming), verification(verified/awaiting/returned/none), expected_remaining_date}.
- Frontend: Sales.jsx PlotDrilldown footer 'Download Payment Report' button (downloadFile blob helper in lib/api.js). PostSalesDashboard.jsx 'Payments · Collections' widget with 7 quick-filter chips + table + Action link to /sales (Record/Correct/View).
- Verified: backend curl (valid %PDF 107KB, all 6 sections via analyze) + testing agent iteration_19 = backend 6/6, frontend 3-role download + widget render/filter/action = 100%, no issues. DB left clean (sold=0/payments=0). Reusable test: /app/backend/tests/test_payment_report_and_collections.py (needs demo booking re-seeded to run).

---
## PHASE 12 — "Editorial Tech" premium UI redesign · PHASE 1 of 4 (2026-06)
- New permanent product-level design directive from founder: elevate from generic SaaS dashboard to a desirable, editorial + technical-instrument, premium enterprise product. Design system authored at /app/design_guidelines.json (design_agent). Theme kept LIGHT (founder choice). Brand logos are WHITE → shown on near-black "brand plates".
- New brand assets in /app/frontend/public: agrocorp-mark-white.webp, agrocorp-arch-white.webp (cropped mark for tiles), group-logo-white.webp, report-logo.png (group logo on dark plate, used in PDF report). PDF report header now uses report-logo.png.
- Design tokens (index.css + tailwind.config.js): added colors line #e7e4dc, plate #1a1c18, lime #ccff00, powder #e8f0fe; utilities .panel/.brandplate/.navlink/.hairline/.kbd2/.grid-canvas/.kpi-value; softened .card (cool 1px border, minimal shadow); prefers-reduced-motion guard.
- Shell REBUILT (Layout.jsx): sidebar → sticky EDITORIAL TOP NAV command centre — brand plate + Management Dashboard/Stakeholder Console, horizontal nav (active = lime underline), ⌘K command palette trigger, notifications, profile; mobile hamburger sheet. Role/permission nav filtering preserved.
- New CommandPalette.jsx (⌘K / Ctrl+K): jump-to nav + debounced /api/search records, full keyboard nav.
- ui.jsx: added AnimatedNumber (rolling/interpolating figures, reduced-motion aware) + inrShort (₹ K/L/Cr).
- Login.jsx + ResetPassword.jsx restyled (dark editorial brand canvas, white group logo, big Cormorant serif, refined form).
- AdminDashboard.jsx redesigned: editorial header, HERO 'Total Received' rolling number + collection-rate bar, per-project analytical panels (progress + component pivot bars), Procurement + Site Bills panels.
- Added ErrorBoundary.jsx wrapping route content in Layout (a page crash no longer blanks the shell).
- Verified: testing agent iteration_20 = frontend 13/13 (100%) after fixing one pre-existing bug (Projects.jsx ProjectCard missing `readOnly` destructure — now fixed). Shell, ⌘K, dashboards, all 6 pages, mobile 390px + 1440px all pass. Demo data cleaned (sold=0/payments=0).
- REMAINING REDESIGN PHASES (not yet done): P2 Units as spatial availability canvas + Projects; P3 Sales & Payments (maker-checker queue/drilldown/collections) + Cancellations; P4 Procurement pipeline timeline + Team/access + Post Sales/Accounts/Site Manager/Management dashboards. Apply the same design DNA; progressively refactor older pages (they currently inherit the softened tokens but still use legacy compositions).

---
## PHASE 12 · Redesign PHASE 2 of 4 — Units availability canvas + Projects (2026-06)
- Units.jsx rebuilt: per-project tables → SPATIAL AVAILABILITY CANVAS. Editorial project header + availability meter (Available/Sold/Booked segments) + legend + status filter chips (filter-<pid>-all/-available/-sold) + responsive tile grid (2/3/4/5 cols). PlotTile shows plot number (mono), status accent bar+dot+label, extent, PLC chips, inline role-gated actions (edit/sell/cancel). All dialogs (UploadWizard/PlotDialog/SellDialog/CancelDialog) + testids UNCHANGED. Added loading skeleton (no empty-state flash).
- Projects.jsx: editorial header (matches Dashboard/Units); cards inherit new tokens; readOnly guard intact.
- ui.jsx Modal: added Escape-to-close + line-token borders + serif title.
- Verified: testing agent iteration_21 = frontend 100%, zero console errors; full book→cancel cycle on plot 32; filters/meter/tiles correct; Post Sales vs Admin action gating correct; mobile 390px no overflow. DB restored sold=0/payments=0.
- Remaining: P3 Sales & Payments (verification queue/drilldown/collections) + Cancellations; P4 Procurement pipeline timeline + Team/access + Post Sales/Accounts/Site Manager/Management dashboards.

---
## PHASE 12 · Redesign PHASE 3 of 4 — Sales & Payments (2026-06)
- Sales.jsx restyled to editorial language (VISUAL ONLY, logic/testids unchanged): editorial header, unified segmented head tabs (Plots/Site/Verification/Cancellations, active = near-black plate), Summary → panel + kpi-value serif numbers, hairline (border-line) tables, plate active pills. Maker-checker flow untouched.
- ui.jsx Modal: Escape-to-close applies across all dialogs (Plot drilldown, Record/Correct payment, etc.).
- Verified: testing agent iteration_22 = frontend 100%, zero bugs; all 4 tabs, drilldown, verify YES/NO, record-payment dialog, cancellations, PDF download, Escape-close, responsive all pass. DB restored sold=0/payments=0.
- Remaining: P4 Procurement pipeline timeline + Team/access + role dashboards (Post Sales/Accounts/Site Manager/Management).

---
## PHASE 12 · Redesign PHASE 4 of 4 — Procurement + Team + role dashboards (2026-06) — REDESIGN PROGRAM COMPLETE
- User choice: Procurement kept TABLE-FOCUSED (not a hero timeline) + a compact 4-step stage tracker (Site→Mgmt→Admin→Accounts) as the approval-state visualization. All logic/permissions/testids preserved (VISUAL ONLY).
- Procurement.jsx: editorial header + Active queue/History as clean .panel + .hairline TABLES (Request / Priority / Stage / Est. value / Documents / Action). New StageTrack dots (done=plate, active=lime ring, todo=grey) keyed off REACHED map by status; rejected shows a red inline chip. Notes + milestone chips nested in the Request cell. All dialogs (New/Action/PO/Milestone) kept, borders swapped agborder→line; StageTrack also shown in ActionDialog.
- Users.jsx: editorial 'Team' header with Meta counts (Members / Awaiting Setup) + hairline table + per-role colored chips (ROLE_TONE). AddMember + AccessModal unchanged in logic (management project + 6 perm-* checkboxes conditional).
- Dashboards restyled to the AdminDashboard/Sales editorial DNA (overline + big serif greeting + AnimatedNumber/inrShort + .panel/.hairline/.kpi-value, grid-canvas hero where relevant):
  - AccountsDashboard: 'Pending Collections · Portfolio' hero (collection-rate bar) + Received/Booked/Pending hero stack + per-project panels with progress bars.
  - SiteManagerDashboard: 4-cell stat strip (Material/Low Stock/Open/Approved) + Low-Stock bars panel + Procurement requests panel. (Open now also counts pending_management/management_clarification.)
  - ManagementDashboard: approvals KPI + AdminDashboard-style ProjectPanel (component bars) + Procurement-needs-approval + Site Bills.
  - PostSalesDashboard: By-Project availability panels + Collections widget (7 filter chips, plate active pill) + Recent Sales; all collections logic/testids intact.
- Verified: testing agent iteration_23 = frontend 100% (7/7), ZERO console/page errors. Admin approve on the seeded pending_admin request advanced status→approved and swapped Review→Issue PO (maker-checker intact). Role nav gating intact. Responsive 390px overflow=0 on /procurement + /users. DB restored clean (procurement=0, sold=0, payments=0, users=3).
- ACTION FOR USER: Redeploy to push the full redesigned UI to production. The 4-phase 'Editorial Tech' redesign program is now COMPLETE across every page/dashboard.

---
## PHASE 13 · Workflow + UX enhancements batch (2026-06)
- **Procurement approval reorder** (backend + frontend): flow is now **Site Manager → Admin → Management → Accounts**. Admin approves FIRST; if the project has a Management user assigned, it moves to `pending_management`, else short-circuits to `approved`. Management approval then sets `approved` → Accounts (PO + milestones). server.py: create_procurement always starts `pending_admin`+notifies admin; `/action` approve computes pending_management-vs-approved; `/mgmt-action` approve → approved+notify accounts. Frontend StageTrack reordered to Site→Admin→Mgmt→Accounts (REACHED map updated). Verified via curl (both paths) + testing agent.
- **View Payment Report (in-app PDF modal)**: new `components/ReportViewer.jsx` fetches `/units/<id>/payment-report` as a blob and shows it in an embedded iframe inside a Modal (new `2xl` size) with a Download button. Added `fetchPdfUrl()` to api.js. Wired into (a) Units sold-plot tiles (icon `view-report-<plot>`, all roles except site_manager) and (b) Sales plot drilldown footer next to Download (`view-report-<unitId>`).
- **Project switch** (`ProjectSwitch` in ui.jsx): both Projects and Units pages now show a top segmented toggle and render ONE project at a time (removes long scroll). testid `project-switch` / `project-switch-<id>`.
- **Auto-logout**: 5-min inactivity timer in Layout.jsx (mouse/keydown/scroll/touch/click reset) → toast + logout.
- **Team column**: Projects column shows 'All projects' for non project-scoped roles (was '—').
- **Login redesign**: split dark/light layout matching user screenshot — left dark panel with group-logo lockup + 'Real-time visibility…' tagline + lime accent dot + brand tile; right Sign in form.
- Verified: testing agent iteration_24 = frontend 100% (11/11), zero console errors. DB restored clean (users 3, sold 0, payments 0, procurement 0).
- ACTION FOR USER: Redeploy to push these changes to production.

---
## PHASE 14 · Report branding + bulk export (2026-06)
- **PDF letterhead + signature**: `_build_report_pdf` now renders a proper letterhead ("AGROCORP GROUP" + Agrocorp/Vacation Village/Landshare logo lockup + "Real estate reimagined" tagline), a "PAYMENT STATEMENT" title band with statement date + project·plot·customer subline, and a bottom **signature block** (Authorised Signatory — For Agrocorp Group | Customer Acknowledgement — <customer>). Verified via analyze_file_tool on generated PDF.
- **Bulk report export**: new `GET /api/projects/{project_id}/payment-reports.zip` (require_report_access; admin/accounts/post_sales/mgmt-with-perm) builds one PDF per SOLD unit (via asyncio.to_thread) and streams a ZIP. Verified: 2 sold plots → zip with 2 valid PDFs.
- Frontend: Sales "Plots" head → each project SectionCard has an "All reports (ZIP)" button (testid `bulk-zip-<projectId>`) for admin/accounts, calling downloadFile on the zip endpoint with a "Preparing…" state. Screenshot-confirmed.
- DB restored clean (users 3, sold 0, payments 0).
- ACTION FOR USER: Redeploy to push to production. Company address/contact can be added to the letterhead if provided.
- **Letterhead contact line added** (2026-06): report letterhead now includes registered office "No.07 Level 3, Vista Pixel 8/2B & 8/2C, Bellary Road Jakkuru, Bengaluru, 560092" and "T +91 9513242807 · info@agrocorp.co.in". Verified via PDF text extraction. Redeploy to push live.
- **GST tax-summary box** (2026-06): `_plot_report_data` now returns `gst_components`/`gst_total` (components whose label contains "GST"); PDF renders a compact "Tax Summary (GST)" table (each GST line + bold Total GST) right after Component Structure. Verified on a generated report (5 GST lines → Total GST Rs. 1,61,078). Redeploy to push live.
- **Project-specific branding** (2026-06): added logo assets `frontend/public/proj-cvf.png` (Central Vista Farms brown wordmark) and `proj-vv.png` (Vacation Village blue snowflake, converted from webp). `_build_report_pdf` now picks the letterhead logo by project name ("central vista"→CVF, "vacation village"→VV, else group). App also shows the per-project logo on Projects cards and the Units project header via `projectLogo(name)` helper in ui.jsx. Verified: CVF PDF shows CVF logo, VV PDF shows VV logo; Projects card shows CVF logo. Redeploy to push live.
- **Project logo everywhere + amount in words** (2026-06): project logo now also shows in Sales project section headers and all per-project dashboard panels (Admin/Accounts/Management/PostSales) via `projectLogo`. PDF statement adds a "Total payable in words: Rupees … Only" line (Indian lakh/crore words via `_num_to_words_in`/`_amount_words`) under Payment Summary. Verified on generated PDF + dashboard screenshot. Redeploy to push live.
- **Formatting + branding refinements** (2026-06):
  - Amounts no longer force-rounded: `inr`/`num2` (frontend) and `_inr_plain` (backend PDF) now show NO decimals for whole numbers and exactly 2 decimals when a fraction exists (e.g., Rs. 10,00,000 vs Rs. 2,50,000.50). `inrShort` (dashboard KPI L/Cr abbreviations) intentionally unchanged.
  - PDF letterhead stripped of extra branding: removed "AGROCORP GROUP" name, address and phone/email; header is now ONLY the per-project logo. Signature line no longer says "For Agrocorp Group".
  - Favicon set to the Agrocorp arch mark (white arch on dark rounded tile → `frontend/public/favicon.png`); browser tab title changed to "Management Console" in `public/index.html`.
  - Verified: PDF header confirmed logo-only with no company text/address/contact; total shows Rs. …43 decimals; page title/favicon confirmed. Redeploy to push live.

---
## PHASE 15 · Verification breakdown, white-screen hardening, PDF logo center (2026-06)
- **Accounts see allocation breakdown**: `VerificationQueue` (Sales → Verification) now renders a sub-row per pending/returned/verified receipt showing each component allocation as chips (e.g., BSP: ₹4,23,000 · 18% GST: ₹77,000) + note + expected-remaining date. If no allocation was provided, shows "recorded as a lump-sum amount". Same chips also added to the PlotDrilldown receipt rows. Verified via seeded post-sales receipt + accounts screenshot.
- **White-screen hardening** (reported on PRODUCTION, intermittent): the existing ErrorBoundary only wrapped page content inside Layout — a crash in Layout/Router/AuthProvider/Login produced a blank white screen. Added a ROOT ErrorBoundary in App.js wrapping all Routes, and `componentDidCatch` now console.errors `[AppError]` + component stack so the real cause is visible. NOTE: exact trigger not reproduced (intermittent, prod-only; likely stale-cache chunk after deploy or a prod-data render edge). If it recurs after redeploy, capture the `[AppError]` console line.
- **PDF logo centered**: report letterhead logo alignment changed LEFT→CENTER. Verified via PDF structure analysis.
- DB restored clean (sold 0, payments 0). Redeploy to push all to production.

---
## PHASE 16 · Component-verified reconciliation fix + dashboard amounts (2026-06)
- **CRITICAL PDF fix — component "Verified Received" column**: REMOVED the earlier fabricated pro-rata spread that pushed ~10% of any un-bifurcated receipt into every component (user reported this as wrong on production Plot 1 / cs1.pdf, where a ₹4,54,755 receipt recorded under "BSP Collection" showed as 10% across all rows). New logic in `_plot_report_data` (`backend/server.py`):
  - Receipts WITH stored allocations → summed by component key (unchanged).
  - Legacy receipts with NO allocations → `_map_head_to_key()` maps the payment head to a component (BSP Collection→basic sale price, PLC→plc, Registration→registration, Maintenance→maintenance) and the FULL receipt amount goes to that one component; everything else stays ₹0.
  - Truly unmappable un-bifurcated receipts go to `unbifurcated_verified` (shown as a note under the table, NOT spread).
  - Verified via curl+PDF extraction: legacy BSP receipt → BSP row ₹4,54,755, all others ₹0; explicit 2-component split + a bifurcated receipt reconcile exactly to Payment Summary Verified Received (₹6,59,755). Decimals confirmed (Rs. 34,177.68 whole vs Rs. 59,33,625).
- **New endpoint** `PATCH /api/payments/{pid}/receipts/{rcid}/allocations` (Accounts-only) lets Accounts bifurcate/re-bifurcate an existing receipt at source; validates alloc total == receipt amount. Tested: 200 ok, 400 on mismatch, 403 for post_sales.
- **Frontend Sales.jsx**: PlotDrilldown receipt rows now show a "Bifurcate" action (testid `bifurcate-<receiptId>`) for Accounts on any VERIFIED receipt with no breakdown → opens `AllocationEditor` modal (mirrors ReceiptDialog allocation UI). Endpoint verified via curl; button UI not browser-tested (needs a seeded sold plot).
- **Dashboard amounts**: all money on Admin/Accounts/Management/PostSales dashboards now use full Indian `inr` format (no rounding, 2-dp only when fractional) with `amountWords()` "Rupees … Only" line beneath each KPI/MiniStat (replaced `inrShort` abbreviations). "Sold value by component" table amounts (Admin + Management) enlarged to `text-lg font-bold` + full `inr`. Smoke-tested via Accounts dashboard screenshot (renders clean).
- DB restored clean (sold 0, payments 0). ACTION FOR USER: Redeploy to push to production; existing production statements will recompute correctly on regeneration, and any legacy lump receipts that don't auto-map can be fixed via the Accounts "Bifurcate" button.

---
## PHASE 17 · Bulk re-bifurcate legacy receipts (2026-06)
- **New endpoint** `POST /api/projects/{project_id}/receipts/auto-bifurcate` (Accounts/Admin). Scans every VERIFIED receipt in the project with no stored allocations; if `_map_head_to_key(head)` resolves (BSP/PLC/Registration/Maintenance), persists the FULL amount as that component's allocation (`action: auto_bifurcated`). Vague/blank-head receipts ("Booking Amount"/"Installment Payment"/"Other") are SKIPPED (never guessed, per user choice) and returned in `skipped_details` (unit_id, plot, buyer, instalment, amount, date, head). Returns `{mapped, skipped, skipped_details}`. Idempotent (2nd run maps 0). Verified via curl: mapped 1 / skipped 1, persisted BSP alloc, post_sales→403.
- **Frontend Sales.jsx** (Plots head): each project SectionCard now has a "Reconcile legacy receipts" button (testid `reconcile-legacy-<projectId>`, Wand2 icon, Accounts/Admin) with a confirm dialog. On success → toast "Auto-split N · M need manual bifurcation"; if M>0 opens a modal listing the skipped receipts with an "Open plot" action (testid `open-plot-<receiptId>`) that jumps to the PlotDrilldown where the existing per-receipt "Bifurcate" button finishes the job.
- DB restored clean (sold 0, payments 0). ACTION FOR USER: Redeploy to push to production; run once per project to reconcile historic lump receipts, then hand-split the few skipped ones.

---
## PHASE 18 · Auto-total, final-price statements, period selector (2026-08)
Diagnosed a production data gap (plots 1/31/34 Vacation Village): each plot carried THREE possibly-divergent numbers — component sum, hand-typed Grand Total (`unit.total`, used by PDF), and `final_price` (used by Sales UI). Fixes shipped:
- **Auto-sum Grand Total (Edit Plot)** — `PlotDialog` (Units.jsx): the `total`-tagged field is now read-only and live-sums all `charge`-tagged fields (dynamic per project's column map). Saved value always = charge sum. Verified in browser (live update + readonly).
- **PDF Total Payable → Final Price** — `_plot_report_data` now uses `final_price or total` (was `total or final_price`), so the payment statement "Total Payable"/Outstanding match the Sales UI "Billed"/Official balance. Per user decision (final price stays manually editable for negotiated deals). Verified: PDF total = final_price 80,82,622.43.
- **Recompute Grand Totals** — `POST /api/projects/{id}/recompute-totals` (admin + post_sales; accounts→403). Re-sums charge cols → sets `unit.total` and the total-tagged column for every plot; returns {updated, changed, changed_details}. Idempotent. Button on Units page header (testid `recompute-<projectId>`) with confirm. Verified via curl (fixed 35/47 CVF plots whose seeded totals didn't match component sums).
- **Dashboard date-range (Collections Outlook)** — new `GET /api/dashboard/collections?months=1|3|6|12` (role/project scoped): for a forward window from today, returns Expected (Σ instalments due in window) vs Received (Σ verified against those instalments) + Outstanding, overall and per-project. New reusable `components/CollectionsPeriod.jsx` (selector 1M/3M/6M/12M, testids `range-<m>`, `period-expected/collected/outstanding`) added to Admin, Accounts, Management, PostSales dashboards. Verified via curl (window math + collected) and browser (selector switches window).
- Preview DB restored clean (sold 0, payments 0). NOTE: recompute in preview rewrote CVF plot totals to their true component sums (seed data had mismatches) — expected. ACTION FOR USER: Redeploy; then run "Recompute totals" once per project so existing plots' Grand Totals equal their component sums.

---
## PHASE 19 · Overdue alerts, price guardrail, CSV export, recompute preview (2026-08)
- **Overdue alerts** in Collections Outlook: `_collections_data` now also flags every instalment with a parseable due_date < today and unpaid balance (`overdue: {total, count, items[{plot,buyer,due_date,days_overdue,outstanding}]}`). `CollectionsPeriod.jsx` shows a clay warning banner (testid `overdue-alert`, chips `overdue-item-<plot>`). Verified browser + curl (1 overdue ₹2,50,000, 15d).
- **Final-Price guardrail** at booking: `SellDialog` (Units.jsx) shows an inline warn (testid `s-price-warning`) when |final_price − unit.total| ≥ ₹1, telling the user the gap and suggesting the Grand Total. Non-blocking (negotiated prices allowed). Verified in browser.
- **Period CSV export**: `GET /api/dashboard/collections.csv?months=N` (admin+accounts; post_sales→403) streams per-instalment rows (Project, Plot, Buyer, Instalment, Due, Expected, Received, Outstanding) + TOTAL + an OVERDUE section. `CollectionsPeriod` "Export CSV" button (testid `collections-export`) for admin/accounts via downloadFile. Verified via curl.
- **Recompute preview**: `recompute-totals` now takes `?dry_run=true` (computes before/after, delta; writes nothing). Units "Recompute totals" first runs dry-run and opens a preview Modal (testid `recompute-apply`, rows `recompute-row-<plot>`) listing current→new→change; Apply performs the real write. Verified browser (modal shows 1 plot +₹25,000) + curl (dry_run no mutation, apply fixes).
- Refactored collections into shared `_collections_data(user, months)`. Preview DB restored clean (sold 0, payments 0). ACTION FOR USER: Redeploy to push to production.

---
## PHASE 20 · Post-Sales schedule editing (2026-08)
- **New endpoint** `PUT /api/units/{unit_id}/schedule` (post_sales ONLY; admin/accounts→403). Body `{installments:[{payment_id?, due_date, amount, notes}]}`. Full restructure of a booked plot's plan: edit name/due/amount, add (no payment_id → new Payment), remove (existing payment_id absent from list). Guardrails: (a) an existing instalment's amount can't be < its verified receipts sum → 400; (b) an instalment with ANY receipt can't be removed → 400; (c) amounts must be > 0. Existing instalments keep their receipts; status/paid_amount recomputed via `_recompute_payment`. Re-sequences seq 1..N in submitted order. Notifies admin+accounts. No forced total==final_price. Verified via curl (valid edit 200 w/ receipt preserved as 'partial'; below-verified 400; remove-with-receipt 400; accounts 403).
- **Frontend** `ScheduleEditor` in Sales.jsx: "Edit schedule" button on PlotDrilldown (testid `edit-schedule-<unitId>`, post_sales via canRecord). Modal lists rows (name/due-date or "On Offer of Possession" toggle/amount), Add instalment (`sched-add`), per-row remove (`sched-remove-<i>`, disabled when the row has receipts), shows "min ₹X verified" under amounts that already have verified money, and a live Schedule total vs Final Price hint (`sched-gap`). Saves via PUT. Verified in browser.
- Preview DB restored clean (sold 0, payments 0). ACTION FOR USER: Redeploy to push to production.

---
## PHASE 21 · Schedule change log / audit (2026-08)
- **New collection** `schedule_logs`. Helper `_log_schedule(unit, action, user, before, after)` records who/when + before/after instalment snapshots (notes/due_date/amount) and count/total deltas. Logged on `sell_unit` (action "created", before=[]) and `edit_schedule` (action "edited", before=prior schedule). `_sched_snap()` builds ordered snapshots.
- **New endpoint** `GET /api/units/{unit_id}/schedule-log` (admin/accounts/post_sales/management) → entries newest-first.
- **Frontend** `ScheduleLog` + `LogSide` in Sales.jsx: "History" button on PlotDrilldown (testid `schedule-log-<unitId>`, all roles that reach the drilldown) opens a modal showing each event — Created/Edited badge, by_name + role, timestamp, count/total delta, and a Before→After side-by-side instalment list. Verified in browser + curl (2 entries with correct before/after).
- Preview DB restored clean (sold 0, payments 0, schedule_logs cleared for test unit). ACTION FOR USER: Redeploy to push to production.

---
## PHASE 22 · Receipt audit trail (2026-08)
- Backend already appends a per-receipt `history` array (submitted/returned/resubmitted/verified/bifurcated/auto_bifurcated) with by_name + at + reason; `/payments` returns it and `_verify_rows` exposes it. No backend change needed.
- **Frontend** `ReceiptTrail` + `buildTrail` in Sales.jsx: a History-icon button on every receipt row in PlotDrilldown (testid `trail-<receiptId>`) AND an "Audit trail" link in each VerificationQueue row (testid `vq-trail-<receiptId>`) opens a timeline modal (steps `trail-step-<i>`) showing Recorded → Returned (with reason) → Corrected & resubmitted → Verified, each with who + when. `buildTrail` falls back to synthesizing from submitted/verified/returned fields for legacy receipts lacking `history`.
- Verified via curl (full history captured) + browser (timeline modal renders all four steps with colors/reason). Preview DB restored clean.
- Note (minor, not fixed): `verify_receipt` currently allows verifying a "returned" receipt directly (only blocks already-"verified"); UI never triggers this since returned receipts show "Correct", not YES/NO.

---
## PHASE 23 · Activity feed + component card = billed vs received (2026-08)
- **"Sold value by component" card reworked → "Received by component"** (Admin + Management dashboards). Backend `_projects_overview` pivots now return, per CHARGE component: `billed` (Σ unit.data[key] over sold plots) and `received` (Σ VERIFIED receipt allocations for that key across the project — explicit bifurcation only, no fallback). Grand Total row is now COMPUTED as the exact sum of the component rows (key `__grand_total__`), so it can never mismatch (fixes point 1). Card shows "₹billed · ₹received" per row with a received/billed progress bar. Frontend AdminDashboard + ManagementDashboard updated (`pv.billed`/`pv.received`, testid `pivot-<key>`).
- **Report reconciliation (point 3/D)**: removed the head→component read-time fallback in `_plot_report_data`; component "Verified Received" now comes ONLY from explicit receipt allocations. Un-bifurcated verified money shows in the existing note. So the payment report and the dashboard card always agree.
- **Activity Feed (Admin only)**: new `GET /api/activity?project_id=&limit=` (require_roles admin) merges schedule_logs (sale booked / schedule edited) + every receipt history event (recorded/verified/returned/corrected/bifurcated) into one timeline, newest first, with actor/plot/project/detail. New `components/ActivityFeed.jsx` added to AdminDashboard with project filter chips (testids `activity-proj-*`, rows `activity-<i>`). Verified curl (6 events, 403 for post_sales) + browser.
- Point 4: existing "Bifurcate" (per receipt) + "Reconcile legacy receipts" (bulk) tools already let Post-Sales (re)enter component splits; un-bifurcated plots now visibly show ₹0 received per component until fixed. (No extra "needs bifurcation" list built — can add if requested.)
- Preview DB restored clean (sold 0). ACTION FOR USER: Redeploy to production; run "Recompute totals" + bifurcate/reconcile receipts so the Received-by-component and reports reflect real splits.

---
## PHASE 24 · Fix "Sold value" vs component Grand Total gap (2026-08)
- User saw Admin project panel "Sold value" (₹15,45,96,299) ≠ component card "Grand Total · Billed" (₹15,46,16,303), a ~₹20k gap. Root cause: `booked_value` summed each sold plot's STORED `unit.total` (drifted, e.g. Plot 34 was −₹20,000), while the pivot Grand Total sums the LIVE component values.
- Fix in `_projects_overview`: `booked` is now `Σ over sold plots of Σ charge-component values` — identical to the pivot Grand Total (Billed) by construction, so "Sold value", the % progress, and Outstanding can never diverge from the component card again, regardless of stored-total drift. Verified via curl: even with a corrupted stored total, booked_value == pivot grand total billed exactly.
- Note: this affects only dashboard aggregates; per-plot PDF/Sales "Billed" still use final_price (Phase 18). Preview DB restored clean.

---
## PHASE 25 · Needs-Bifurcation list (2026-08)
- **New endpoint** `GET /api/needs-bifurcation?project_id=` (admin/accounts/post_sales): for each sold plot, sums verified receipts with NO allocations → returns items {unit_id, plot_number, buyer, project, verified, unbifurcated, receipts} sorted by unbifurcated desc, plus grand {total,count}. Verified via curl (lump plot listed with unbif ₹3,00,000; fully-bifurcated plot excluded).
- **Frontend** `NeedsBifurcation` panel in Sales.jsx, shown at top of the Plots view for admin/accounts/post_sales: collapsible amber banner "N sold plot(s) have ₹X verified but not yet split by component" + table (Plot/Buyer/Project/Verified/Un-bifurcated/Receipts) with a "Bifurcate" action opening the PlotDrilldown. Auto-refetches when the Sales data reloads (refresh prop). Verified in browser.
- Preview DB restored clean (sold 0). ACTION FOR USER: Redeploy; this surfaces exactly which plots make up the header-vs-component "Received" gap so Post-Sales can split them.

---
## PHASE 26 · Total Payable = Grand Total, schedule check (2026-08)
- User bug: report "Total Payable" (₹45,50,000 = final_price) ≠ Edit-Plot "Grand Total" (₹45,47,547). USER DECISION: Total Payable must equal the Grand Total, the schedule must add up to the Grand Total, enforced by a check; Total Payable is fetched from the schedule.
- Backend: `_plot_report_data` total_payable = Σ instalment amounts (schedule sum; fallback final_price/total only if no schedule). `sell_unit` + `edit_schedule` now REJECT (400) when schedule total differs from the plot's Grand Total (Σ charge-tagged column values) by >₹1.
- Frontend: `ScheduleEditor` now takes `grandTotal`, disables Save unless schedule total == Grand Total, shows "Matches Grand Total ✓" / "Under|Over Grand Total by ₹X — adjust to save" (testids sched-total, sched-gap). PlotDrilldown computes grandTotal from charge components.
- Existing Phase-20 schedule editing + Phase-19/23 component/bifurcation editing confirmed present. testing_agent iteration_25 = 100% (7/7 backend + frontend). New pytest: /app/backend/tests/test_schedule_grand_total.py. DB clean (0 sold, 0 payments).
- ACTION FOR USER: Redeploy. For existing production plots where schedule ≠ Grand Total (e.g. Plot 1: ₹45,50,000 vs ₹45,47,547), Post-Sales opens "Edit schedule" and adjusts an instalment so it sums to the Grand Total — then Total Payable shows the Grand Total.

---
## PHASE 27 · Auto-Fit Schedule + Flag Mismatched Plots (2026-06)
- **New endpoint** `GET /api/mismatched-plots?project_id=` (admin + post_sales; accounts→403): every SOLD plot whose Σ instalment amounts ≠ Grand Total (Σ charge-tagged columns) by >₹1. Returns per plot {grand_total, schedule_total, difference, installments:[{payment_id,notes,due_date,amount,verified}]}, sorted by |difference| desc, + grand {total,count}.
- **New endpoint** `POST /api/units/{unit_id}/auto-fit-schedule` body `{payment_id}` (admin + post_sales; accounts→403): snaps the schedule to the Grand Total by adjusting the CHOSEN instalment by the exact difference. BLOCKS (400, clear message) if the new amount would fall below that instalment's verified-received amount, or ≤0. Logs a schedule "edited" audit entry + notifies admin/accounts. Helpers `_plot_grand_total`, `_verified_of`.
- **Frontend** `components/MismatchedPlots.jsx`: red collapsible panel (testid `mismatched-plots`) listing mismatched plots with Grand Total / Schedule / signed Difference; per row `autofit-open-<plot>` opens `AutoFitPicker` modal (testid `autofit-picker`) — user PICKS which instalment absorbs the diff (radios `autofit-pick-<pid>`, below-verified options disabled), `autofit-apply` calls the endpoint. Optional "Open plot" (`mismatch-open-<plot>`). Wired into Sales → Plots (admin+post_sales) + Admin dashboard + Post Sales dashboard (below Collections outlook).
- **Frontend** Sales.jsx `ScheduleEditor`: added per-row "Fit here" button (testid `sched-fit-<i>`, shown only when total ≠ Grand Total) that snaps THAT row so the schedule matches; blocks (toast) if it would drop below verified. Complements the existing equality-required Save.
- User choices honoured: Auto-Fit in BOTH the editor and the list; user picks the instalment each time; below-verified snaps blocked with a clear message; list on BOTH Sales and dashboards; Post Sales + Admin only.
- Verified: testing_agent iteration_26 = 100% backend perms + full UI flows, 0 bugs; DB left clean (sold=0, payments=0). Reusable tests: /app/backend/tests/test_autofit_flow.py, test_autofit_perms.py, seed_autofit.py, cleanup_autofit.py.
- ACTION FOR USER: Redeploy. Then on production, open a dashboard or Sales → Plots to see any plots whose schedule drifted from the Grand Total and fix each with one click via Auto-Fit.

---
## PHASE 28 · Full payment-plan edit + Accounts re-approval of paid revisions (2026-06)
- **Card action changed**: the Mismatched Plots card now opens a FULL payment-plan editor ("Edit payment plan", testid `edit-plan-<plot>`) instead of the single-instalment Auto-Fit picker. Reps can edit/add/remove any instalment; the per-row "Fit here" quick-snap remains inside the editor; Save stays blocked until the schedule sums to the Grand Total.
- **ScheduleEditor extracted** to `components/ScheduleEditor.jsx` (exported), reused by the mismatched card (Sales + both dashboards) and the plot drilldown. Shows a `sched-paid-warning` banner + per-row "Paid · needs re-approval" label when instalments have receipts.
- **Paid-instalment revisions → Accounts re-approval**: `PUT /units/{id}/schedule` now returns `{revision_raised}` and, when a change touches a PAID instalment (has any receipt of any status), inserts a `schedule_revisions` doc + notifies Accounts. Change saves immediately (informational approval per default).
- **New endpoints**: `GET /api/schedule-revisions?status=&project_id=` (accounts+admin; post_sales→403) and `POST /api/schedule-revisions/{id}/review` (marks approved, double-approve→400).
- **New "Schedule Revisions" tab** in Sales → Payments (testid `head-revisions`, admin/accounts only) with pending/approved filters, before→after view of each changed paid instalment (`revision-affected-<id>-<i>`), and a "Recheck & approve" action (`revision-approve-<id>`).
- User choices honoured: card → single "Edit payment plan"; "already paid" = any receipt; revisions land in the new Schedule Revisions tab; Grand-Total equality still enforced on Save.
- Verified: testing_agent iteration_27 = 100% backend + frontend, 0 bugs; DB left clean (sold=0, payments=0, revisions=0). Tests: test_autofit_flow.py, test_schedule_revision.py, seed_ui_mismatch.py.
- ACTION FOR USER: Redeploy to push these changes to production.


## PHASE 29 · Bifurcation Progress (2026-06)
- **New endpoint** `GET /api/bifurcation-progress?project_id=` (admin, accounts, post_sales, management): per project, share of VERIFIED money already split by component = Σ(verified receipts WITH allocations) ÷ Σ(all verified). Returns per-project {verified, bifurcated, unbifurcated, pending_receipts, pct} sorted least-reconciled first, plus portfolio totals.
- **New component** `components/BifurcationProgress.jsx`: collapsible panel (testid `bifurcation-progress`) with a colour-coded progress bar per project (`bif-bar-<pid>`), showing bifurcated/verified, %, and "₹X across N receipt(s) still to bifurcate". Shown on Sales → Plots for admin/accounts/post_sales, above the Needs-Bifurcation panel. Renders nothing when no verified money exists.
- Verified: backend test /app/backend/tests/test_bifurcation_progress.py (62.5% split math, pending count, roles) passes; DB left clean. Frontend compiles; panel reuses the tested Needs-Bifurcation pattern.
- ACTION FOR USER: Redeploy to push live.

## PHASE 30 · CVF inventory fix + The Vault add-on + stream-aware dashboard (2026-06)
CVF-only work; Vacation Village (proj_53fb360c1f0a, 256 units) untouched throughout.
### Phase 1 — CVF data + tagging (applied to preview DB)
- Retagged the 4 PLC columns (East Facing / Corner / CV Facing / 2-or-more PLC) from `ignore`→`charge`; PLC values were dropped at import so also **backfilled** them from the inventory sheet + refreshed each plot's `net_payable`/`total`. Now Grand Total (Σ charge cols) == inventory NET PAYABLE for all 47 (verified 47/47).
- Added the **54 missing farms** (1–31, 33–37, 39, 49–52, 79–84, 90–94, 99, 100) as AVAILABLE plots with zero values → CVF now has **101 plots**.
- Scripts: /app/backend/tests/phase1_cvf_inventory.py (run with `apply`).
### Phase 2 — The Vault (optional add-on at booking)
- Project-scoped `project.vault_config` on CVF (4 variants: 7000/8000/8000-2BR/10000 with construction+GST totals, + a 10×10% schedule template). Seed: tests/seed_cvf_vault_config.py. VV has none.
- `Payment.stream` field ("land" default / "vault"). Unit gets `vault:{enabled,variant_id,label,construction,gst,total}` when booked with Vault.
- `sell_unit` accepts optional `vault` + `vault_schedule`; validates land schedule == Grand Total AND vault schedule == Vault total; creates separate stream="vault" payments.
- `edit_schedule` is stream-aware (`stream` param; validates per-stream total; only touches that stream's payments).
- `mismatched_plots` evaluates BOTH streams per plot; items carry `stream`/`stream_label`.
- Frontend: Units SellDialog "Add The Vault" toggle + variant + prefilled Vault schedule (testids vault-toggle/variant/total/sched-total/gap). Sales PlotDrilldown shows Land + Vault sections + two edit buttons (edit-schedule-<uid>, edit-vault-schedule-<uid>). ScheduleEditor takes `stream`. MismatchedPlots shows a Stream column and per-stream editing.
### Phase 3 — Option B stream-aware dashboard
- `_projects_overview` returns per-project `streams{land,vault{...,attach_count}}` + `has_vault`, and consolidated land/vault booked/received + `vault_attach`.
- Admin dashboard: "Revenue by stream" panel (Land vs Vault columns, vault-attach badge) + per-project Land/Vault split (dash-streams-<pid>). Projects without Vault (VV) render no Vault UI. Management consolidated includes Vault.
- Verified: tests/test_vault_flow.py (ALL PASS) + testing_agent iteration_28 (100% FE+BE, 0 bugs). DB pristine: CVF 101 available + vault_config, VV 256 untouched.
- ACTION FOR USER: Redeploy to push live. When booking a CVF plot you'll now see 'Add The Vault'; the dashboard splits Land vs Vault revenue.
## PHASE 31 · CVF component-display fix + Vault-in-PDF + newspaper dashboard (2026-06)
- **Root cause of the "only 4 PLC components" bug:** it was on PRODUCTION — Phase-1 was a preview-DB data change, and a redeploy ships code, not preview data, so production's CVF column tags were stale. (All values were ₹0 simply because CVF has 0 sold.)
- **Fix (self-healing):** added idempotent startup migration `_migrate_cvf()` (server.py), matched by project NAME, that sets CVF's canonical column tags (all real charge heads → `charge`) and seeds `vault_config`. Runs on every boot → production self-heals on redeploy. No-op on preview (already correct). Never touches VV.
- **Vault in statement PDF:** `_plot_report_data` now splits Land vs Vault streams; the PDF shows "Payment Plan — Land" + a "The Vault — Construction Add-on" summary + "The Vault — Payment Plan" table. Verified by tests/test_vault_pdf.py.
- **Newspaper dashboard (Option C):** scoped `.newsdash` theme in index.css (Playfair Display headings, flat sharp-bordered cardless sections, masthead double-rule, Land=#4a4a4a / Vault=#9bbad4). Applied to BOTH Admin & Management dashboards + StreamPanel/StreamMini. Purely visual — no functionality change. VV shows no Vault UI.
- Verified: testing_agent iteration_29 (100% BE+FE, 0 bugs); DB pristine (CVF 101 available + vault_config, VV 256). Tests: test_vault_pdf.py, test_vault_flow.py.
- ACTION FOR USER: **Redeploy** so production picks up the migration (fixes the component list) + the Vault PDF + the newspaper dashboard.

## PHASE 32 · Newspaper dashboard polish (2026-06)
- Added broadsheet detailing to the `.newsdash` theme (index.css): nameplate masthead (`nd-masthead`), drop-cap on the greeting headline (`header h1::first-letter`), 2px dark top rules on top-level section panels, powder-blue kicker markers before uppercase `.overline` labels, stronger column/section rules. Applied on Admin + Management dashboards. Purely visual, scoped, no functionality change.
- Verified: testing_agent iteration_30 (100% FE, 0 bugs) — renders flawlessly at 1440 & 1920, no overflow/overlap/console errors, CSS does not leak to Sales/Units.
- ACTION FOR USER: Redeploy to see it on production.

## PHASE 33 · Production CVF self-heal (real root cause) (2026-06)
- User screenshots (production) revealed CVF was STRUCTURALLY broken there: its columns were only the 4 PLCs + 2 blank reference fields (no BSP/GST/NET PAYABLE), and Edit Plot showed only those fields. Preview and production CVF data were entirely different; a redeploy ships code, not preview data, and the previous retag-only migration couldn't fix columns that don't exist in prod.
- Fix: exported the canonical CVF definition from preview to `backend/cvf_seed.json` (24 columns + 101 units' data + vault_config). Rewrote `_migrate_cvf` (server.py, startup, matched by project NAME): if CVF is broken (missing bsp/net_payable columns) it rebuilds the full column set and heals each AVAILABLE plot's data from the seed; always ensures vault_config. Never touches sold plots or any other project (VV safe). Idempotent — after one heal, columns contain bsp so subsequent boots skip the rebuild.
- Verified end-to-end: simulated the exact production breakage on preview (8 cols, no vault, blanked plot) → restart → healed to 24 cols/19 charge, vault restored, plot data exact (₹82,53,782.22), 101 units, VV 256. Backend logged "CVF project healed" + "plots healed=101 added=0".
- ACTION FOR USER: **Redeploy** — production will self-heal on boot (component list, plot data, and Vault config all restored). This is what fixes the live "only 4 PLC components" issue.

## PHASE 34 · CVF DEVELOPMENT CHARGE field restored (2026-06)
- Mismatch: the edit form skipped "DEVELOPMENT CHARGE" (sheet col #5) because `development_charge` was tagged `ignore` (₹0 on every plot) and the form hides ignore columns. Retagged it to `charge` in _CVF_TAGS (server.py), cvf_seed.json, and the live preview project. CVF now shows all 24 columns (Plot number + 23 fields = the full sheet). Grand Total unchanged (dev charge = ₹0). Migration tag-ensure keeps it on every boot → production self-heals on redeploy.
- ACTION FOR USER: Redeploy to apply on production.

---
## PHASE 35 · Procurement PI workflow — item bifurcation, notes visibility, Tax Invoice, "Upload new PI" loop (2026-06)
- User requirements: 1 PI = 1 independent request (SM can raise many); a PI has multiple line items each with own qty + est cost (bifurcation); Admin must see SM's notes; flow Site Manager → Admin → Management (optional, only if a mgmt user is assigned) → Accounts → PO issued → Tax Invoice/receipts; Accounts uploads PO + can leave a comment for SM; "ask for a new PI" keeps the request open so SM re-uploads a fresh PI to the SAME request.
- Backend (server.py, already present + verified): ProcurementRequest has pi_amount, accounts_note, tax_invoice_file. POST /procurement accepts pi_amount+notes+items. POST /procurement/{id}/action (approve/reject/clarify) — clarify → pending_clarification; approve routes to pending_management if a mgmt user is on the project else approved. POST /procurement/{id}/mgmt-action. POST /procurement/{id}/po accepts po_number+note+file (accounts_note). POST /procurement/{id}/tax-invoice. POST /procurement/{id}/resubmit-pi reopens request as pending_admin with fresh pi_file + revised items + pi_amount. download_file fails GRACEFULLY (404 with a clear message) if the object is missing in this environment (preview/prod storage are separate) — mitigates the production "server error" on attachment view.
- Frontend (Procurement.jsx) — THIS session: (a) converted the item-bifurcation mismatch from a HARD BLOCK to a SOFT, non-blocking warning (proc-bif-hint; submission always succeeds; per user, a single-item PI needs no split). (b) Added the Site Manager "Upload new PI" button (resubmit-<request_id>) on pending_clarification/management_clarification + new ResubmitDialog (shows what Admin asked, prefills items, uploads a new PI file + revised items + pi_amount → reopens pending_admin). Admin Review dialog already shows SM notes (review-sm-notes) + PI amount + per-item qty/cost; PoDialog has po-note + optional tax invoice; Documents column links PI/PO/Tax.
- Verified: testing_agent iteration_31 = backend 10/10 + full UI flow 100%, ZERO bugs (SM create with bifurcation mismatch submits; Admin sees SM notes; clarify→resubmit loop; Admin approve→Management→Accounts PO+note+tax invoice; docs/download 200). Pytest: /app/backend/tests/test_procurement_e2e.py. Preview DB cleaned (procurement=0); test users removed.
- OPEN (optional, not requested): no admin DELETE /procurement/{id} endpoint; single-item bifurcation hint suppressed by design.
- ACTION FOR USER: Redeploy to push to production. For the production attachment "server error": after redeploy, re-upload + open a PI/PO/Tax file on the LIVE app (preview files don't exist in prod storage). If it still errors on prod only, it likely needs Emergent Support (cross-environment object storage).

---
## PHASE 36 · Admin cancel procurement request (2026-06)
- User ask: admin action to cancel a procurement request raised in error, with a short reason kept on record.
- Backend (server.py): POST /api/procurement/{id}/cancel (admin only, ProcCancel{reason}) — reason required (400 if blank), 400 if already cancelled; sets status="cancelled" + cancel_reason/cancelled_by/cancelled_by_name/cancelled_at; notifies the requester + accounts. Added "cancelled" to the ProcurementRequest status Literal.
- Frontend (Procurement.jsx): admin "Cancel" button (data-testid cancel-<request_id>, Ban icon) on every non-terminal request (not paid/rejected/cancelled) → CancelProcDialog (data-testid cancel-reason / cancel-submit) requiring a reason. Cancelled requests fall into the History bucket; StageTrack shows a grey "Cancelled" chip; the cancel reason + who shows in the request notes. StatusPill: added cancelled (grey "Cancelled").
- Verified: curl (400 no-reason, 200 with reason, 400 double-cancel) + screenshot (Cancel button in Action column + dialog opens). Preview procurement=0 after cleanup.
- ACTION FOR USER: Redeploy to push to production.
