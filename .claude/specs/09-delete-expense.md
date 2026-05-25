# Spec: Delete Expense

## Overview
This step implements the "Delete Expense" feature, allowing a logged-in user to permanently remove an expense they own. A delete button appears next to each expense row on the profile page. Clicking it submits a POST request to confirm and execute the deletion; the user is then redirected back to their profile. Ownership is enforced at the DB layer so no user can delete another user's data. This completes the full CRUD lifecycle for expenses in Spendly.

## Depends on
- Step 01 — Database Setup (`expenses` table must exist)
- Step 03 — Login/Logout (session-based auth required)
- Step 04/05 — Profile page (source of delete buttons and redirect target)
- Step 07 — Add Expense (`expenses` rows must exist to delete)
- Step 08 — Edit Expense (per-row action pattern in profile table follows the same conventions)

## Routes
- `POST /expenses/<int:id>/delete` — verify ownership, delete the expense, redirect to `/profile` — logged-in only

> The existing stub in `app.py` uses `GET`. Replace it with `POST` to prevent accidental or cross-site deletion via crafted links.

## Database changes
No new tables or columns. One new DB helper is required in `database/db.py`:
- `delete_expense(expense_id, user_id)` — deletes the expense row; includes `user_id` in the `WHERE` clause so users can only delete their own expenses. Returns the number of rows deleted (0 or 1).

The existing `get_expense_by_id(expense_id, user_id)` helper (added in Step 08) is reused for the ownership pre-check before deletion.

## Templates
- **Create:** None — no separate confirmation page; deletion is triggered directly from the profile table.
- **Modify:** `templates/profile.html` — add a delete form (method POST) per expense row with a `confirm()` JavaScript guard to prevent accidental deletion. The form action must use `url_for('delete_expense', id=expense.id)`.

## Files to change
- `app.py` — replace the `delete_expense` stub with a POST-only route; import `delete_expense` from `database/db.py`
- `database/db.py` — add `delete_expense(expense_id, user_id)` helper
- `templates/profile.html` — add a delete button/form per expense row alongside the existing edit link

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not applicable here, but never store raw passwords)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Route must be `POST` only — decorate with `methods=["POST"]` and remove the GET stub
- Redirect unauthenticated users to `/login` using `session.get("user_id")`
- Ownership enforcement: `delete_expense` must include `user_id` in its `WHERE` clause — never rely on route-level ownership checks alone
- Pre-check with `get_expense_by_id` before deleting; if it returns `None`, call `abort(404)`
- If `delete_expense` returns 0 rows (race condition or tampered ID), call `abort(404)`
- On success, redirect to `url_for('profile')`
- Delete button in `profile.html` must be wrapped in a `<form method="POST">` — no plain anchor `<a href>` for the delete action
- Add a JavaScript `confirm()` call on the form's `onsubmit` event to prevent accidental deletion
- All DB logic goes in `database/db.py`, not inline in the route

## Definition of done
- [ ] Sending a POST to `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] Sending a POST to `/expenses/<id>/delete` for a non-existent expense returns 404
- [ ] Sending a POST to `/expenses/<id>/delete` for an expense owned by a different user returns 404
- [ ] Sending a POST to `/expenses/<id>/delete` for an owned expense deletes the row from the DB
- [ ] After a successful delete, the user is redirected to `/profile` and the deleted expense no longer appears in the table
- [ ] Each expense row on the profile page has a working delete button that triggers a `confirm()` dialog before submitting
- [ ] Cancelling the `confirm()` dialog does NOT submit the form and the expense is NOT deleted
- [ ] The existing GET stub (`GET /expenses/<id>/delete`) no longer returns a plain string — only POST is handled
- [ ] No other user's expenses are affected after a delete
