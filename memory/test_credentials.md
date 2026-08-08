# Test Credentials — Agrocorp Lite

## Sole Admin login
- Name: Debabrata
- Phone: `9513242807`
- Password: `Repro@123`  (must_reset_password = FALSE for testing convenience)
- Role: admin

## Auth model
- Login by PHONE + PASSWORD. New users: initial password = phone, forced reset on first login.
- Admin "Reset password" (Team page) resets a user's password back to their phone number.

## Env (backend/.env)
- MONGO_URL=mongodb://localhost:27017 · DB_NAME=agrocorp_lite · ADMIN_PHONE=9999999999

## Data state (Phase 1)
- Projects (2): Vacation Village Chikkamagaluru (proj_53fb360c1f0a, 256 plots, OLD schema — no columns yet), Central Vista Farms (proj_01d7e89ba838, 47 plots, NEW dynamic schema with 24 columns saved)
- All plots status=available; payments/procurement/inventory/notifications empty
- Only the admin user exists

## Dynamic inventory model (Phase 1)
- Project.columns = [{key,label,tag}] tag ∈ plot_id|area|charge|total|reference|ignore
- Unit has generic `data`{key:value}, plus `area`, `total`, `plot_number`, `status`
- Upload flow: POST /units/preview (returns columns+suggested tags) → POST /units/commit (project_id, file, mapping JSON)
- Add plot: POST /projects/{id}/plots {plot_number,data}; Edit: PATCH /units/{unit_id} {plot_number,data}
- Dashboard returns by_project[] (pivots per charge/total/reference column) + consolidated
