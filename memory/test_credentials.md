# Test Credentials (preview)

- Admin: phone `9513242807` / password `Repro@123` (view-only for record/verify)
- Post Sales: phone `9000000001` / password `Pass@123` (records payments)
- Accounts: phone `9000000002` / password `Pass@123` (verifies payments)

Projects: CVF `proj_01d7e89ba838` (47 plots), Vacation Village `proj_53fb360c1f0a` (256 plots). Rates: CVF 2500, VV 3200.

## Payment maker-checker (Phase 9)
- Post Sales books plot + creates schedule, then records payments (pending) with components/mode/head/expected-remaining-date.
- Accounts verifies YES (posts to official totals) or NO (returns with reason); Post Sales corrects & resubmits.
- Only VERIFIED receipts count in paid_amount / dashboards. Admin dashboard shows "Awaiting Verify" per project.
