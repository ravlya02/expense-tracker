# Spec: Date Filter For Profile

## Overview
This feature adds a client-side date range filter to the expense table on the profile page. Users can select a start date and end date to narrow the visible expense rows without a full page reload. The filter operates entirely in the browser via vanilla JS — no new routes are needed. This keeps the server simple while giving users a fast, interactive way to review expenses within a specific period.

## Depends on
- Step 04 — Profile Page Design (renders `profile.html` with the expense table)
- Step 05 — Backend Routes for Profile Page (`get_expenses_by_user` returns all expenses)

## Routes
No new routes.

## Database changes
No database changes.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date-range filter form (two `<input type="date">` fields: "From" and "To") above the expense table
  - Add `data-date` attributes to each expense table row so JS can read the date value
  - Wire up a JS call to filter rows on input change

## Files to change
- `templates/profile.html` — add filter UI and `data-date` row attributes
- `static/js/main.js` — add `filterExpensesByDate()` function and event listeners

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Filter logic must be pure vanilla JS — no libraries, no fetch calls
- The filter must be additive: if only "From" is set, hide rows before that date; if only "To" is set, hide rows after that date; if neither is set, show all rows
- Date comparison must use ISO 8601 string comparison (`YYYY-MM-DD`) — no JS Date parsing required
- The `data-date` attribute on each `<tr>` must be the raw `YYYY-MM-DD` value from the database
- Filter inputs should have `id="filter-from"` and `id="filter-to"` for reliable JS targeting
- If no rows are visible after filtering, display a "No expenses match the selected dates." message in the table body
- Do not add a submit button — filtering must be reactive (fires on every `input` event)

## Definition of done
- [ ] Profile page renders a "From" date input and a "To" date input above the expense table
- [ ] Entering a "From" date hides all expense rows with a date earlier than the selected value
- [ ] Entering a "To" date hides all expense rows with a date later than the selected value
- [ ] Setting both "From" and "To" shows only rows within the inclusive range
- [ ] Clearing both inputs restores all rows
- [ ] When the filter produces zero visible rows, a "No expenses match the selected dates." message appears in the table
- [ ] The filter works with the seeded demo data (dates span 2026-05-01 to 2026-05-18)
- [ ] No page reload occurs when the filter inputs change
- [ ] Existing profile page layout and stats section are unaffected
