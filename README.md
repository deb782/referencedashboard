# Agrocorp Lite

A stripped-down post-sales & site-operations admin for a plotted real-estate developer. Same domain as the full Agrocorp Admin, but with only the workflows that a lean team actually needs on day one.

## Team roles (4 only)

| Role | Can do |
|---|---|
| **Admin** | Creates projects, adds team members, uploads unit inventory Excel, reviews procurement requests |
| **Post-Sales Rep** | Marks a plot as sold with buyer details + a payment schedule |
| **Accounts** | Marks each scheduled payment received/pending; records PO number + payment for approved procurement |
| **Site Manager** | Manages inventory for their project; raises procurement requests |

## Core flows

### Sales
Admin uploads RERA Excel → 256 units land in the system → Post-Sales picks any available plot, enters buyer/date/final-price/booking-amount + a payment schedule table → Accounts + Admin get in-app notification → Accounts marks each row received or pending on the due date.

### Procurement
Site Manager raises a request (subject + item list + priority + notes) → Admin gets in-app notification → Admin approves / rejects / marks "needs clarification" with a note → if approved, Accounts gets notified → Accounts records PO number + paid amount + date.

### Inventory
Site Manager freely adds/edits/deletes on-site materials (`name, quantity, unit, notes`). No auto-linking to procurement — kept intentionally simple.

## No email, no cron
Notifications are in-app only. There's no scheduled reminder engine — Accounts just eyeballs the due-date column.

## Auth
Phone number is the initial password. Every new user is forced to set a new password on first login. No forgot-password flow; if someone forgets, an admin clicks "Reset password" to reset it back to their phone number.

## Stack
- Backend: FastAPI + Motor (async MongoDB) + PyJWT + bcrypt + openpyxl
- Frontend: React 19 + React Router v7 + Tailwind + Sonner + Lucide icons
- Single-file backend (~600 lines), 8 frontend pages
- No shadcn/ui, no query library — plain axios + hooks

## Repository layout

```
/
├── backend/
│   ├── server.py            # Single-file FastAPI app
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   ├── index.css
│   │   ├── lib/{api.js,auth.jsx}
│   │   ├── components/Layout.jsx
│   │   └── pages/{Login,ResetPassword,Dashboard,Projects,Users,Units,Sales,Inventory,Procurement}.jsx
│   ├── public/index.html
│   ├── package.json
│   ├── craco.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.example
├── .emergent/emergent.yml
└── memory/PRD.md
```

## Local run

**Backend:**
```bash
cd backend
cp .env.example .env         # edit MONGO_URL, JWT_SECRET
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Frontend:**
```bash
cd frontend
cp .env.example .env         # set REACT_APP_BACKEND_URL (e.g. http://localhost:8001)
yarn install
yarn start
```

## First login

- **Phone:** `9999999999` (from `ADMIN_PHONE` in backend `.env`)
- **Password:** `9999999999` (same as phone — initial)
- You'll be forced to set a new password on first login.

## Data model

- `users` — 4 roles, phone as unique index
- `projects` — with optional `site_manager_id`
- `units` — imported from Excel; store `plc_details` + `other_charges` as reference dicts
- `payments` — one row per installment (`seq`, `due_date`, `amount`, `status` = pending | received)
- `procurement` — status flow: pending_admin → (pending_clarification) → approved → paid | rejected
- `inventory` — flat, free-form
- `notifications` — in-app bell items

## Endpoints (28 total)

- `auth/*` (3): login, me, change-password
- `users/*` (5): CRUD + admin reset password
- `projects/*` (4): CRUD
- `units/*` (3): list, import (Excel), sell (with schedule)
- `payments/*` (2): list, patch status
- `procurement/*` (4): list, create, admin action, record payment
- `inventory/*` (4): list, create, patch, delete
- `notifications/*` (3): list, mark read, mark all read
- `dashboard` (1)
- `health` (2)
