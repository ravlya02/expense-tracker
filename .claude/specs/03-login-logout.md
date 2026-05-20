# Spec: Login and Logout

## Overview
This step adds session-based authentication to Spendly. Users can log in with their email and password, receive a Flask session cookie, and log out to clear it. It also wires up the `/logout` stub route and adds a `get_user_by_email` helper to the DB layer. After this step, the app knows who is logged in and can guard future routes accordingly.

## Depends on
- Step 01 — Database Setup (users table, `get_db()`)
- Step 02 — Registration (`create_user`, password hashing with werkzeug)

## Routes
- `POST /login` — validate credentials, set session, redirect to `/` — public
- `GET /logout` — clear session, redirect to `/login` — public (currently a stub)

(`GET /login` already renders `login.html` — no change needed to the GET handler beyond ensuring it redirects logged-in users.)

## Database changes
No new tables or columns.

Add one new helper to `database/db.py`:
- `get_user_by_email(email)` — returns the matching row as a `sqlite3.Row` (or `None` if not found), using a parameterized query.

## Templates
- **Modify:** `templates/login.html` — ensure the form has `method="POST"` and `action="{{ url_for('login') }}"`, and displays an `{{ error }}` block when passed from the route.
- **Modify:** `templates/base.html` — update the navbar: when `session` contains a user, show a "Log out" link (`url_for('logout')`); otherwise show "Sign in" (`url_for('login')`) and "Get started" (`url_for('register')`).

## Files to change
- `app.py` — add `POST /login` logic; replace `/logout` stub with real implementation; set `app.secret_key` if not already set.
- `database/db.py` — add `get_user_by_email(email)`.
- `templates/login.html` — form attributes and error display.
- `templates/base.html` — session-aware navbar links.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via Flask.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only.
- Parameterized queries only — never f-strings in SQL.
- Password verification with `werkzeug.security.check_password_hash` — never compare plain text.
- Session stores only `user_id` and `user_name` — never store the password hash in the session.
- Use CSS variables — never hardcode hex values in templates or stylesheets.
- All templates extend `base.html`.
- `app.secret_key` must be set before any `session` usage; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`).
- On login failure, re-render `login.html` with a generic error (`"Invalid email or password."`) — never reveal which field was wrong.
- After successful login, redirect to `/` with `url_for('index')`.
- Logout must use `session.clear()` (or `session.pop`) then redirect to `url_for('login')`.
- Do **not** implement a login-required decorator or middleware in this step — that belongs to a later step.

## Definition of done
- [ ] Visiting `/login` while already logged in still renders the login page (no redirect yet — that's a later step).
- [ ] Submitting the login form with the demo credentials (`demo@spendly.com` / `demo123`) redirects to `/`.
- [ ] Submitting with a wrong password re-renders the login form with the error `"Invalid email or password."`.
- [ ] Submitting with an unknown email re-renders the login form with the same generic error.
- [ ] After login, `session['user_id']` and `session['user_name']` are set (verifiable via Flask shell or a quick print in the route).
- [ ] Visiting `/logout` clears the session and redirects to `/login`.
- [ ] The navbar shows "Log out" when a session exists, and "Sign in" / "Get started" when it does not.
- [ ] All existing tests pass (`pytest`).
