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
