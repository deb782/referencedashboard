# Test Credentials — Agrocorp Lite

## Admin (primary, auto-provisioned)
- Phone: `9999999999`
- Password: `Repro@123`  (was reset by main agent during bug repro; user should change via app)
- Role: admin
- must_reset_password: false

## Other seeded users (created by user during their session; passwords unknown/user-set)
- Phone `9513242807` — role admin (must_reset_password: true, initial pw = phone `9513242807`)
- Phone `6204253887` — role site_manager (must_reset_password: true, initial pw = phone `6204253887`)

## Auth model
- Login is by PHONE + PASSWORD (not email).
- New users get initial password = their phone number, forced reset on first login.
- No forgot-password flow; admin "Reset password" resets a user back to their phone number.

## Env (backend/.env)
- MONGO_URL=mongodb://localhost:27017
- DB_NAME=agrocorp_lite
- ADMIN_PHONE=9999999999
- ADMIN_EMAIL=admin@agrocorp.com

## Existing data (do NOT wipe — user's working data)
- Projects: proj_53fb360c1f0a (Vacation Village Chikkamagaluru), proj_01d7e89ba838 (Central Vista Farms)
- ~256 units imported into Vacation Village; a couple already sold.
