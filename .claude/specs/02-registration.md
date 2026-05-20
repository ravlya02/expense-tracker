# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step wires up the `POST /register` route to validate form input, hash the password, insert a new row into the `users` table, and redirect to the login page on success. The registration form template already exists — this step adds the backend logic that makes it functional.

## Depends on
- Step 01 — Database Setup (`get_db()`, `init_db()`, `users` table must exist)

## Routes
- `GET /register` — already implemented, renders `register.html` — public
- `POST /register` — **new** — handles form submission, inserts user, redirects — public

## Database changes
No new tables or columns. Uses the existing `users` table:
- `name` TEXT NOT NULL
- `email` TEXT UNIQUE NOT NULL
- `password_hash` TEXT NOT NULL

## Templates
- **Modify:** `templates/register.html` — add `method="POST"` and `action="{{ url_for('register') }}"` to the form; add `name` attributes to all inputs; display flash error messages

## Files to change
- `app.py` — add `POST` method to `/register` route; add form-handling logic; import `redirect`, `url_for`, `request`, `flash`, `session` from Flask
- `database/db.py` — add `create_user(name, email, password)` helper
- `templates/register.html` — wire up form attributes and flash message display

## Files to create
None

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already available.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` — never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic (`create_user`) goes in `database/db.py`, not inline in the route
- The route must use `abort(400)` / `abort(500)` for HTTP errors, not bare string returns
- Duplicate email must be caught (sqlite3.IntegrityError) and shown as a flash error, not a 500
- On success redirect to `url_for('login')` — do not render a template directly
- `app.secret_key` must be set for `flash()` to work — add it to `app.py` if missing
- Validate that name, email, and password are non-empty before hitting the DB; show flash errors for missing fields

## Definition of done
- [ ] Submitting the form with valid data creates a new user row in `users` with a hashed password
- [ ] Submitting with a duplicate email shows a flash error and does not create a duplicate row
- [ ] Submitting with any blank field shows a flash error and does not hit the DB
- [ ] Successful registration redirects to `/login`
- [ ] Passwords are never stored in plaintext — `password_hash` column contains a werkzeug hash
- [ ] App starts without errors
- [ ] All SQL uses `?` placeholders — no string interpolation
