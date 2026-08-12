# Test Credentials (preview)

- Admin: phone `9513242807` / password `Repro@123` (view-only for record/verify)
- Post Sales: phone `9000000001` / password `Pass@123` (records payments)
- Accounts: phone `9000000002` / password `Pass@123` (verifies payments)

Projects: CVF `proj_01d7e89ba838` (47 plots), Vacation Village `proj_53fb360c1f0a` (256 plots). Rates: CVF 2500, VV 3200.

## Payment maker-checker (Phase 9)
- Post Sales books plot + creates schedule, then records payments (pending) with components/mode/head/expected-remaining-date.
- Accounts verifies YES (posts to official totals) or NO (returns with reason); Post Sales corrects & resubmits.
- Only VERIFIED receipts count in paid_amount / dashboards. Admin dashboard shows "Awaiting Verify" per project.

## Management role (Phase 10)
- No standing management user in preview (create via admin Team page). Admin creates: role Management, pick ONE project, tick sections (Projects/Team/Units/Sales & Payments/Inventory/Procurement). Initial password = phone; user resets on first login. Edit access later via the row's access (sliders) button.
- Management is view-only everywhere; only action is procurement PRIMARY approval. Procurement now routes Site Manager -> Management (if assigned to that project) -> Admin -> Accounts.
- Test users used during E2E (deleted after): Management `9000000003`, Site Manager `9000000004` (both initial pwd = phone).

