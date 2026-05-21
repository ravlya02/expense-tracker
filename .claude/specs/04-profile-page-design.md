# Spec: Profile Page Design

## Overview
This feature replaces the `/profile` stub route with a fully designed, styled profile page showing hardcoded UI. The goal is to establish the complete visual layout — user info card, summary stats, transaction history table, and category breakdown — before any real database queries are wired up. Building the UI first lets us validate the design in isolation and ensures the templates and styles are ready for the data-connection step.

## Depends on
- Step 1: Database setup (schema must exist, `get_db()` / `init_db()` / `seed_db()` must be implemented)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/profile` must be a protected route)

## Routes
- `GET /profile` — render the profile page — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient.

## Templates
- **Create:** `templates/profile.html` — full profile page extending `base.html`; contains four sections:
  1. **User info card** — avatar initials circle, name, email, member-since date (all hardcoded)
  2. **Summary stats row** — total spent, number of transactions, top category (hardcoded)
  3. **Transaction history table** — list of recent expenses with date, description, category badge, amount (hardcoded rows)
  4. **Category breakdown** — per-category totals displayed as progress-bar rows (hardcoded)
- **Modify:** `templates/base.html` — update the logged-in navbar branch to display `session.get('user_name')` alongside the logout link

## Files to change
- `app.py` — replace the `/profile` stub with a real view function that:
  - Redirects unauthenticated users to `/login` using `session.get("user_id")`
  - Passes hardcoded context variables (user info dict, stats dict, expense list, category list) to `profile.html`
- `templates/base.html` — show the logged-in user's name in the navbar

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles for the profile layout (imported via `{% block head %}`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` if any DB call is ever added
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables from `style.css` — never hardcode hex values (use `var(--accent)`, `var(--paper-card)`, etc.)
- All templates extend `base.html`
- No inline `<style>` tags — page-specific styles go in `static/css/profile.css`
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- All data passed to the template must be hardcoded Python dicts/lists in `app.py` — no DB queries in this step
- Category badges must use a CSS class, not inline colour styles
- Avatar circle must display initials derived from the hardcoded name, not an `<img>` tag

## Definition of done
- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] Visiting `/profile` while logged in returns HTTP 200
- [ ] The page displays a user info card with avatar initials, name, and email
- [ ] The page displays at least three summary stat values (total spent, transaction count, top category)
- [ ] The page displays a transaction history table with at least three hardcoded rows, each with date, description, category badge, and amount
- [ ] The page displays a category breakdown section with at least three categories shown as progress-bar rows
- [ ] The navbar shows the logged-in user's name alongside the logout link
- [ ] No hex colour values appear in `profile.html` or `profile.css` — only CSS variables
- [ ] No inline `<style>` blocks anywhere in `profile.html`
- [ ] Page is visually consistent with the existing `style.css` design system (fonts, spacing, radius tokens)
