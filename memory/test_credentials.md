# Test Credentials — Agrocorp Lite (publish-ready state)

## Sole Admin login
- Name: Debabrata
- Phone: `9513242807`
- Initial password: `9513242807` (same as phone)
- must_reset_password: TRUE → forced to set a new password on first login

## Auth model
- Login is by PHONE + PASSWORD.
- New users get initial password = their phone number, forced reset on first login.
- Admin "Reset password" resets a user back to their phone number.

## Env (backend/.env)
- MONGO_URL=mongodb://localhost:27017
- DB_NAME=agrocorp_lite
- ADMIN_PHONE=9999999999  (only used to auto-provision if users collection is EMPTY; not empty now)

## Data state (post reset, 2026-08-06 — pre-publish)
- Projects (2): Vacation Village Chikkamagaluru (proj_53fb360c1f0a, 256 plots), Central Vista Farms (proj_01d7e89ba838, 47 plots)
- Units: 303 total, ALL status=available, buyer/sale fields cleared
- payments / procurement / inventory / notifications: empty
- Users: only the admin above
