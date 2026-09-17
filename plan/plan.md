# Feature: PO progress updates → installment-by-installment payments

## Goal
After a PO is issued, tie each installment of payment to an item/activity of
work, and give the Site Manager a way to report progress ("this item/activity
is done") so Admin, Management and Accounts are notified and Accounts can
release the next installment.

## How it fits what exists today
- The Site Manager already breaks the PI into items with quantities and costs.
- Accounts already sets a "payment structure" — a list of installments (each has
  a label, an amount and a due date) — and marks each installment paid.
- What's missing is the link between doing the work and releasing the next
  payment, and a place for the Site Manager to communicate progress.

## What will be added
1. **Activity-based installments.** When Accounts sets up the payment structure,
   each installment can represent an item/activity from the PO (Accounts can
   generate the installments straight from the PI items, or add custom activity
   lines). Each installment carries: activity name, amount, due date.

2. **Per-installment work status (Site Manager).** For each installment the Site
   Manager can update a work status — Not started → In progress → Done — and add
   a short note when marking it done (e.g. "Brick work completed at Block A").

3. **A progress/discussion thread on the request (post-PO).** A running comment
   area visible to Site Manager, Admin, Management and Accounts. Every entry
   shows who wrote it, their role, and the time. The Site Manager uses it to
   report progress; the others can reply/ask questions.

4. **Notifications that drive the next payment.** When the Site Manager marks an
   activity Done (or posts a progress note), Admin, Management and Accounts are
   notified — signalling Accounts that the next installment can be released.
   Accounts releasing an installment (already exists) notifies the Site Manager
   that the money is out and work can proceed.

5. **Clear status at a glance.** Each installment shows both its payment state
   (Pending / Paid) and its work state (Not started / In progress / Done), so
   everyone can see, per activity, whether work is done and whether it's been
   paid.

## Decisions for the user
1. **Does completing work gate the next payment, or just signal it?**
   - a. Signal only (recommended): the "Done" mark + notification tells Accounts
     they can release the next installment, but Accounts stays in control and
     can pay in any order.
   - b. Enforce order: Accounts cannot release installment N+1 until the Site
     Manager has marked installment N's work as Done.
   (Default if unspecified: **a — signal only**.)

2. **Who can post in the progress thread?**
   - a. All four roles can post (recommended).
   - b. Only the Site Manager posts progress; Admin/Management/Accounts read only.
   (Default: **a — all four can post**.)

3. **Should marking work "Done" require the installment to already be paid?**
   Your description is: Accounts releases a partial payment → work starts → Site
   Manager marks it done → next installment. That implies work-done comes after
   that installment is paid.
   - a. No hard requirement — Site Manager can mark work done anytime (recommended,
     more flexible).
   - b. Only allow marking work done on installments that are already paid.
   (Default: **a — no hard requirement**.)

## Assumptions
- This progress/comment capability appears only after a PO is issued.
- Site Manager sees only their own project's requests (already the case);
  Admin/Accounts see all; Management sees its permitted projects.
- Notifications are in-app (the app's existing notification system); no email/SMS.
- Amounts and the payment structure continue to be owned by Accounts; the Site
  Manager only reports work progress and comments — they don't change amounts.

## Out of scope (unless requested)
- Attaching photos/files to a progress update (can be added later if wanted).
- Any change to the earlier stages (Site Manager → Admin → Accounts approval).
