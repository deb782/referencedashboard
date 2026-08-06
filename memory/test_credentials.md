# Test Credentials — Agrocorp Lite

## Admin (auto-provisioned on startup)
- Phone: `9999999999`
- Password: `9999999999` (initial = phone; forced reset on first login)
- Role: admin
- Note: On first login the user is forced to set a new password. If a test needs to
  reuse this account after reset, either use the new password set during the test run,
  or drop the `users` collection to re-provision, or use admin "Reset password" (resets to phone).

## Auth model
- Login is by PHONE + PASSWORD (not email).
- New users get initial password = their phone number, forced reset on first login.
- No forgot-password flow; admin "Reset password" resets a user back to their phone number.

## Env (backend/.env)
- MONGO_URL=mongodb://localhost:27017
- DB_NAME=agrocorp_lite
- ADMIN_PHONE=9999999999
- ADMIN_EMAIL=admin@agrocorp.com
