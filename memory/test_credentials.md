# Test Credentials — Agrocorp Lite

## Demo accounts (password reset done; go straight to dashboard)
| Role | Phone | Password |
|------|-------|----------|
| Admin | `9999999999` | `Repro@123` |
| Accounts | `9000000001` | `Accounts@123` |
| Post-Sales Rep | `9000000002` | `Sales@123` |
| Site Manager (proj_53fb360c1f0a) | `9000000003` | `Site@123` |

## Auth model
- Login is by PHONE + PASSWORD (not email).
- New users get initial password = their phone number, forced reset on first login.
- Admin "Reset password" resets a user back to their phone number.

## Env (backend/.env)
- MONGO_URL=mongodb://localhost:27017
- DB_NAME=agrocorp_lite
- ADMIN_PHONE=9999999999

## Existing data (do NOT wipe)
- Projects: proj_53fb360c1f0a (Vacation Village Chikkamagaluru), proj_01d7e89ba838 (Central Vista Farms)
- ~256 units in Vacation Village; 3 sold; 4 pending payments.
