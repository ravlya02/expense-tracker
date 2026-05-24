# Spec: Edit Expense

## Overview
This step implements the "Edit Expense" feature, allowing a logged-in user to update an existing expense they own. The user clicks an edit link next to any expense on their profile page, lands on a pre-filled form, makes changes, and submits. The expense is updated in the database and the user is redirected back to their profile. This is the first update path for expense data in Spendly.

## Depends on
- Step 01 — Database Setup (`expenses` table must exist)
- Step 03 — Login/Logout (session-based auth required)
- Step 04/05 — Profile page (source of edit links and redirect target)
- Step 07 — Add Expense (establishes the expense form pattern this step follows)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with existing expense values — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. Two new DB helpers are required in `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — fetches a single expense row, returns `None` if not found or if `user_id` does not match (ownership check baked in)
- `update_expense(expense_id, user_id, amount, category, date, description)` — updates the expense row; includes `user_id` in the `WHERE` clause to prevent cross-user edits

Additionally, `get_expenses_by_user` currently omits the `id` column from its result rows. It must be updated to include `id` so that profile page templates can build edit links.

## Templates
- **Create:** `templates/edit_expense.html` — edit form extending `base.html`, identical structure to `add_expense.html` but with all fields pre-filled from the existing expense
- **Modify:** `templates/profile.html` — add an edit icon/link per table row that points to `url_for('edit_expense', id=expense.id)`

## Files to change
- `app.py` — replace the `edit_expense` stub with full GET/POST implementation; import new DB helpers
- `database/db.py` — add `get_expense_by_id()` and `update_expense()` helpers; update `get_expenses_by_user()` to return `id`
- `templates/profile.html` — add per-row edit links in the transaction table

## Files to create
- `templates/edit_expense.html`
- `static/css/edit_expense.css`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not applicable here, but never store raw passwords)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect unauthenticated users to `/login` using `session.get("user_id")`
- Ownership enforcement: both `get_expense_by_id` and `update_expense` must include `user_id` in their `WHERE` clause — never rely on route-level checks alone
- If the expense does not exist or belongs to another user, call `abort(404)`
- `amount` must be a positive float — reject zero or negative values
- `category` must be one of the allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` must be a valid date string in `YYYY-MM-DD` format
- `description` is optional (may be empty string or None)
- On validation failure, re-render the form with the error message and the submitted (not original) values
- On success, redirect to `url_for('profile')`
- All DB logic goes in `database/db.py`, not inline in the route

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for a non-existent expense returns 404
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by a different user returns 404
- [ ] Visiting `/expenses/<id>/edit` while logged in and owning the expense renders the form pre-filled with the existing values
- [ ] Submitting the form with all valid fields updates the expense in the DB and redirects to `/profile`
- [ ] The updated expense values appear correctly on the profile page after redirect
- [ ] Submitting with a missing or empty `amount` re-renders the form with an error
- [ ] Submitting with a non-positive `amount` re-renders the form with an error
- [ ] Submitting with an invalid `category` re-renders the form with an error
- [ ] Submitting with a missing `date` re-renders the form with an error
- [ ] Previously submitted (invalid) values are preserved in the form on validation failure
- [ ] Each expense row on the profile page has a working edit link pointing to the correct expense id
