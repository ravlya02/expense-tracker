# Spec: Add Expense

## Overview
This step implements the "Add Expense" feature, allowing a logged-in user to submit a new expense through a form. The form collects amount, category, date, and an optional description. On successful submission the expense is persisted to the `expenses` table and the user is redirected to their profile. This is the first write path for expense data in Spendly.

## Depends on
- Step 01 — Database Setup (`expenses` table must exist)
- Step 03 — Login/Logout (session-based auth required)
- Step 04/05 — Profile page (redirect target after submission)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the new expense, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. The `expenses` table already exists with the required schema:
```
id, user_id, amount, category, date, description, created_at
```
A new DB helper `add_expense(user_id, amount, category, date, description)` must be added to `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form page extending `base.html`

## Files to change
- `app.py` — replace the `add_expense` stub with full GET/POST implementation
- `database/db.py` — add `add_expense()` helper
- `templates/profile.html` — ensure the "Add Expense" button links to `url_for('add_expense')`

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not applicable here, but never store raw passwords)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect unauthenticated users to `/login` using `session.get("user_id")`
- `amount` must be a positive float — reject zero or negative values
- `category` must be one of the allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` must be a valid date string in `YYYY-MM-DD` format
- `description` is optional (may be empty string or None)
- On validation failure, re-render the form with the error message and previously entered values (do not clear the form)
- On success, redirect to `url_for('profile')`
- `add_expense()` DB helper goes in `database/db.py`, not inline in the route
- Import `add_expense` in `app.py` from `database.db`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders the add-expense form
- [ ] Submitting the form with all valid fields saves the expense to the DB and redirects to `/profile`
- [ ] The new expense appears in the profile expense list immediately after submission
- [ ] Submitting with a missing or empty `amount` re-renders the form with an error
- [ ] Submitting with a non-positive `amount` re-renders the form with an error
- [ ] Submitting with an invalid `category` re-renders the form with an error
- [ ] Submitting with a missing `date` re-renders the form with an error
- [ ] Previously entered values are preserved in the form on validation failure
- [ ] The "Add Expense" link on the profile page points to `/expenses/add`
