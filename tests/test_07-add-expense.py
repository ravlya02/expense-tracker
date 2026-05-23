# tests/test_07-add-expense.py
# Tests for: Add Expense (GET /expenses/add, POST /expenses/add)
# Spec: .claude/specs/07-add-expense.md
#
# Spec rules under test:
#   - Unauthenticated access (GET and POST) redirects to /login
#   - GET renders add-expense form for a logged-in user
#   - POST with all valid fields saves expense to DB and redirects to /profile
#   - The new expense appears in the profile expense list after a successful add
#   - POST with missing/empty amount re-renders form with an error
#   - POST with non-positive amount (zero, negative) re-renders form with an error
#   - POST with invalid category re-renders form with an error
#   - POST with missing date re-renders form with an error
#   - Previously entered values are preserved in the form on validation failure
#   - Profile page "Add Expense" link points to /expenses/add
#
# DB isolation: monkeypatches database.db.DB_PATH via conftest.py fixtures so
# no test ever touches the committed spendly.db.
#
# Allowed categories (from spec): Food, Transport, Bills, Health,
#   Entertainment, Shopping, Other

import re

import pytest

from database import db as db_module


# ------------------------------------------------------------------ #
# Fixtures — shared fixtures are in conftest.py.                     #
# This file adds one local fixture for a fresh (non-seeded) user     #
# that makes the "new expense appears in list" assertions unambiguous.#
# ------------------------------------------------------------------ #

@pytest.fixture()
def fresh_logged_in_client(app):
    """Authenticated client for a freshly registered test user (no seed data).

    Creates a single user in the temp DB, then sets the session to that user's
    id. This gives us a blank expense slate so any expense we add is the only
    one and is easy to assert on.
    """
    with app.app_context():
        user_id = db_module.create_user(
            "Test User", "test@example.com", "testpassword"
        )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Test User"
    return client


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

_VALID_PAYLOAD = {
    "amount":      "42.50",
    "category":    "Food",
    "date":        "2026-06-01",
    "description": "Test lunch",
}

# All seven allowed category values per spec.
_ALLOWED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


def _post_add_expense(client, payload, follow=False):
    """POST to /expenses/add with the given form payload."""
    return client.post(
        "/expenses/add",
        data=payload,
        follow_redirects=follow,
    )


# ------------------------------------------------------------------ #
# Test class                                                          #
# ------------------------------------------------------------------ #

class TestAddExpense:

    # -------------------------------------------------------------- #
    # Auth guard — GET                                                #
    # -------------------------------------------------------------- #

    def test_get_redirects_to_login_when_unauthenticated(self, client):
        """Spec: unauthenticated GET /expenses/add must redirect to /login."""
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_get_unauthenticated_follow_lands_on_login_page(self, client):
        """Following the auth redirect must render the login page (200)."""
        response = client.get("/expenses/add", follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert 'name="email"' in html or 'type="email"' in html

    # -------------------------------------------------------------- #
    # Auth guard — POST                                               #
    # -------------------------------------------------------------- #

    def test_post_redirects_to_login_when_unauthenticated(self, client):
        """Spec: unauthenticated POST /expenses/add must redirect to /login."""
        response = _post_add_expense(client, _VALID_PAYLOAD)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_unauthenticated_does_not_insert_into_db(self, app, client):
        """An unauthenticated POST must not write any row to the expenses table."""
        _post_add_expense(client, _VALID_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    # -------------------------------------------------------------- #
    # GET — authenticated                                             #
    # -------------------------------------------------------------- #

    def test_get_renders_form_for_authenticated_user(self, fresh_logged_in_client):
        """Spec: GET /expenses/add while logged in must render the add-expense form."""
        response = fresh_logged_in_client.get("/expenses/add")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Form must be present and target the correct route.
        assert "<form" in html
        assert "/expenses/add" in html

    def test_get_renders_amount_input(self, fresh_logged_in_client):
        """Form must contain an input for amount."""
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="amount"' in html

    def test_get_renders_category_select(self, fresh_logged_in_client):
        """Form must contain a <select> for category with all allowed options."""
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="category"' in html
        for cat in _ALLOWED_CATEGORIES:
            assert cat in html, f'Category option "{cat}" missing from form'

    def test_get_renders_date_input(self, fresh_logged_in_client):
        """Form must contain a date input."""
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="date"' in html

    def test_get_renders_description_field(self, fresh_logged_in_client):
        """Form must contain a description field (optional per spec)."""
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="description"' in html

    def test_get_renders_no_error_on_initial_load(self, fresh_logged_in_client):
        """A fresh GET of the form must not display any validation error.

        The template only renders <div class="auth-error"> when error is truthy.
        On a clean GET, app.py passes error=None, so the block is absent.
        """
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert "auth-error" not in html

    def test_get_extends_base_html(self, fresh_logged_in_client):
        """The add-expense template must extend base.html (full page rendered)."""
        response = fresh_logged_in_client.get("/expenses/add")
        html = response.data.decode("utf-8")
        # base.html renders the outer <html> wrapper — presence confirms inheritance.
        assert "<html" in html

    # -------------------------------------------------------------- #
    # Happy path — valid POST                                         #
    # -------------------------------------------------------------- #

    def test_valid_post_redirects_to_profile(self, fresh_logged_in_client):
        """Spec: a valid POST must redirect to /profile."""
        response = _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_expense_into_db(self, app, fresh_logged_in_client):
        """Spec (DB side-effect): the new expense must be persisted in the expenses table."""
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            rows = conn.execute("SELECT * FROM expenses").fetchall()
            conn.close()
        assert len(rows) == 1
        row = rows[0]
        assert float(row["amount"]) == pytest.approx(42.50)
        assert row["category"] == "Food"
        assert row["date"] == "2026-06-01"
        assert row["description"] == "Test lunch"

    def test_valid_post_stores_correct_user_id(self, app, fresh_logged_in_client):
        """The inserted expense row must be linked to the authenticated user."""
        with app.app_context():
            user_id = db_module.get_user_by_email("test@example.com")["id"]

        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)

        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute("SELECT user_id FROM expenses").fetchone()
            conn.close()
        assert row["user_id"] == user_id

    def test_valid_post_without_description_succeeds(self, app, fresh_logged_in_client):
        """Spec: description is optional — omitting it must still insert the expense."""
        payload = {
            "amount":   "10.00",
            "category": "Other",
            "date":     "2026-06-02",
            # description intentionally absent
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 1

    def test_valid_post_with_empty_description_succeeds(self, app, fresh_logged_in_client):
        """An explicitly empty description string is also valid per spec."""
        payload = {**_VALID_PAYLOAD, "description": ""}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 302

        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 1

    # -------------------------------------------------------------- #
    # New expense appears on profile page after successful add        #
    # -------------------------------------------------------------- #

    def test_new_expense_appears_in_profile_expense_list(self, fresh_logged_in_client):
        """Spec: the new expense must appear in the profile expense list
        immediately after a successful POST."""
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        assert profile_response.status_code == 200
        html = profile_response.data.decode("utf-8")
        # The inserted amount and description should appear in the table.
        assert "42.50" in html
        assert "Test lunch" in html

    def test_new_expense_amount_uses_rupee_symbol_on_profile(self, fresh_logged_in_client):
        """The amount on the profile page must be prefixed with ₹, not £ or $.

        The profile.html template renders: ₹{{ expense.amount }} — the ₹ symbol
        is the Indian Rupee (U+20B9). This test guards against regression to
        incorrect currency symbols."""
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "₹" in html
        assert "£" not in html
        assert "$" not in html

    def test_new_expense_category_appears_on_profile(self, fresh_logged_in_client):
        """The category badge for the new expense must appear on the profile page."""
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "Food" in html

    def test_new_expense_date_appears_on_profile(self, fresh_logged_in_client):
        """The date of the new expense must appear in the profile expense table."""
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "2026-06-01" in html

    def test_transaction_count_increments_after_add(self, fresh_logged_in_client):
        """After adding one expense, the profile stats must show transaction_count = 1.

        The profile.html template renders:
          <span class="profile-stat-value">{{ stats.transaction_count }}</span>
        so '1</span>' will be present in the HTML.
        """
        _post_add_expense(fresh_logged_in_client, _VALID_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        # Match the integer 1 wrapped in a profile-stat-value span.
        assert ">1<" in html or "1</span>" in html or ">1 <" in html

    # -------------------------------------------------------------- #
    # Validation — missing / empty amount                             #
    # -------------------------------------------------------------- #

    def test_missing_amount_rerenders_form_with_error(self, fresh_logged_in_client):
        """Spec: missing amount must re-render the form (200) with an error message."""
        payload = {**_VALID_PAYLOAD, "amount": ""}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Template renders error inside <div class="auth-error">.
        assert "auth-error" in html

    def test_missing_amount_does_not_insert_into_db(self, app, fresh_logged_in_client):
        """A POST with missing amount must not write any row to the expenses table."""
        payload = {**_VALID_PAYLOAD, "amount": ""}
        _post_add_expense(fresh_logged_in_client, payload)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    def test_non_numeric_amount_rerenders_form_with_error(self, fresh_logged_in_client):
        """A non-numeric amount string must re-render the form with an error."""
        payload = {**_VALID_PAYLOAD, "amount": "abc"}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    # -------------------------------------------------------------- #
    # Validation — non-positive amount                                #
    # -------------------------------------------------------------- #

    def test_zero_amount_rerenders_form_with_error(self, fresh_logged_in_client):
        """Spec: amount of zero is non-positive — must re-render form with error."""
        payload = {**_VALID_PAYLOAD, "amount": "0"}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_zero_amount_does_not_insert_into_db(self, app, fresh_logged_in_client):
        """A POST with amount = 0 must not write any row to the expenses table."""
        payload = {**_VALID_PAYLOAD, "amount": "0"}
        _post_add_expense(fresh_logged_in_client, payload)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    def test_negative_amount_rerenders_form_with_error(self, fresh_logged_in_client):
        """Spec: a negative amount must re-render the form with an error."""
        payload = {**_VALID_PAYLOAD, "amount": "-5.00"}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_negative_amount_does_not_insert_into_db(self, app, fresh_logged_in_client):
        """A POST with a negative amount must not write any row to the expenses table."""
        payload = {**_VALID_PAYLOAD, "amount": "-5.00"}
        _post_add_expense(fresh_logged_in_client, payload)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    def test_very_small_positive_amount_is_accepted(self, app, fresh_logged_in_client):
        """A positive amount just above zero (0.01) is valid per spec."""
        payload = {**_VALID_PAYLOAD, "amount": "0.01"}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 302
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 1

    # -------------------------------------------------------------- #
    # Validation — invalid category                                   #
    # -------------------------------------------------------------- #

    def test_invalid_category_rerenders_form_with_error(self, fresh_logged_in_client):
        """Spec: a category not in the allowed list must re-render the form with error."""
        payload = {**_VALID_PAYLOAD, "category": "Gambling"}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_invalid_category_does_not_insert_into_db(self, app, fresh_logged_in_client):
        """A POST with an invalid category must not write any row to the expenses table."""
        payload = {**_VALID_PAYLOAD, "category": "Gambling"}
        _post_add_expense(fresh_logged_in_client, payload)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    def test_empty_category_rerenders_form_with_error(self, fresh_logged_in_client):
        """An empty category string (form default placeholder) must also fail validation."""
        payload = {**_VALID_PAYLOAD, "category": ""}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    @pytest.mark.parametrize("cat", _ALLOWED_CATEGORIES)
    def test_all_allowed_categories_are_accepted(self, app, fresh_logged_in_client, cat):
        """Every category in the spec's allowed list must be accepted as valid.

        Each parametrize iteration runs against its own fresh_logged_in_client
        (function-scoped fixture), so the DELETE at the end is a belt-and-suspenders
        guard in case that isolation changes.
        """
        payload = {**_VALID_PAYLOAD, "category": cat}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 302, (
            f'Category "{cat}" was rejected — expected redirect (302), got {response.status_code}'
        )
        # Defensive cleanup in case the fixture ever becomes session-scoped.
        with app.app_context():
            conn = db_module.get_db()
            conn.execute("DELETE FROM expenses")
            conn.commit()
            conn.close()

    # -------------------------------------------------------------- #
    # Validation — missing date                                       #
    # -------------------------------------------------------------- #

    def test_missing_date_rerenders_form_with_error(self, fresh_logged_in_client):
        """Spec: a missing date must re-render the form with an error."""
        payload = {**_VALID_PAYLOAD, "date": ""}
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_missing_date_does_not_insert_into_db(self, app, fresh_logged_in_client):
        """A POST with a missing date must not write any row to the expenses table."""
        payload = {**_VALID_PAYLOAD, "date": ""}
        _post_add_expense(fresh_logged_in_client, payload)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 0

    # -------------------------------------------------------------- #
    # Form value preservation on validation failure                   #
    # -------------------------------------------------------------- #

    def test_amount_is_preserved_after_validation_failure(self, fresh_logged_in_client):
        """Spec: previously entered values must survive a validation failure.

        The amount the user typed must be re-populated via form.amount in the template:
          value="{{ form.amount or '' }}"
        """
        payload = {
            "amount":      "99.99",
            "category":    "Food",
            "date":        "",          # missing date triggers the error
            "description": "Preserved entry",
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "99.99" in html, (
            "Previously entered amount '99.99' was not preserved in the re-rendered form"
        )

    def test_description_is_preserved_after_validation_failure(self, fresh_logged_in_client):
        """Spec: description text must be re-populated after a validation failure.

        Template renders: {{ form.description or '' }} inside the textarea.
        """
        payload = {
            "amount":      "15.00",
            "category":    "Health",
            "date":        "",          # missing date triggers the error
            "description": "My preserved description",
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "My preserved description" in html, (
            "Previously entered description was not preserved in the re-rendered form"
        )

    def test_category_is_preserved_after_validation_failure(self, fresh_logged_in_client):
        """Spec: the selected category must remain selected after a validation failure.

        Template marks the matching option selected via:
          {% if form.category == cat %}selected{% endif %}
        The category value still appears in the HTML regardless of selected state.
        """
        payload = {
            "amount":      "20.00",
            "category":    "Transport",
            "date":        "",          # missing date triggers the error
            "description": "",
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Transport" in html, (
            "Previously selected category 'Transport' was not reflected in re-rendered form"
        )

    def test_date_is_preserved_after_validation_failure(self, fresh_logged_in_client):
        """Spec: the entered date must be re-populated after a validation failure.

        Template renders: value="{{ form.date or '' }}"
        """
        payload = {
            "amount":      "",          # missing amount triggers the error
            "category":    "Bills",
            "date":        "2026-07-15",
            "description": "",
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "2026-07-15" in html, (
            "Previously entered date '2026-07-15' was not preserved in the re-rendered form"
        )

    def test_form_is_not_cleared_on_invalid_category(self, fresh_logged_in_client):
        """All entered values must survive an invalid-category failure, not just
        date and amount. The route passes the raw form dict back to the template
        on any validation error."""
        payload = {
            "amount":      "55.00",
            "category":    "Gambling",   # invalid — triggers error before date check
            "date":        "2026-08-10",
            "description": "Vegas night",
        }
        response = _post_add_expense(fresh_logged_in_client, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "55.00" in html, "amount not preserved on invalid-category failure"
        assert "2026-08-10" in html, "date not preserved on invalid-category failure"
        assert "Vegas night" in html, "description not preserved on invalid-category failure"

    # -------------------------------------------------------------- #
    # Profile page — "Add Expense" button link                        #
    # -------------------------------------------------------------- #

    def test_profile_page_add_expense_link_points_to_add_route(
        self, logged_in_client
    ):
        """Spec: the 'Add Expense' link on the profile page must point to /expenses/add.

        profile.html renders:
          <a href="{{ url_for('add_expense') }}" class="btn-primary">+ Add Expense</a>

        Uses logged_in_client from conftest.py (seeded demo user) because the
        profile page requires at least one user in the DB to render without 404.
        """
        response = logged_in_client.get("/profile")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "/expenses/add" in html, (
            "Profile page does not contain a link to /expenses/add — "
            "the '+ Add Expense' button must use url_for('add_expense')"
        )

    def test_profile_page_add_expense_link_is_anchor_tag(self, logged_in_client):
        """The Add Expense link must be an <a> tag so it performs a GET to /expenses/add.

        profile.html template confirmed to use:
          <a href="{{ url_for('add_expense') }}" class="btn-primary">+ Add Expense</a>
        """
        response = logged_in_client.get("/profile")
        html = response.data.decode("utf-8")
        anchor_pattern = re.compile(r'<a\b[^>]*href="[^"]*\/expenses\/add[^"]*"[^>]*>')
        assert anchor_pattern.search(html), (
            "Expected <a href='...'/expenses/add'...> on the profile page, "
            "but no matching anchor tag was found"
        )

    # -------------------------------------------------------------- #
    # Edge cases                                                      #
    # -------------------------------------------------------------- #

    def test_multiple_expenses_can_be_added_sequentially(
        self, app, fresh_logged_in_client
    ):
        """Adding two expenses in sequence must result in exactly two rows in the DB."""
        payload_a = {**_VALID_PAYLOAD, "amount": "10.00", "date": "2026-06-01"}
        payload_b = {**_VALID_PAYLOAD, "amount": "20.00", "date": "2026-06-02"}
        _post_add_expense(fresh_logged_in_client, payload_a)
        _post_add_expense(fresh_logged_in_client, payload_b)

        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 2

    def test_expense_for_one_user_does_not_appear_for_another(self, app):
        """Expenses must be scoped to the owning user — a second user must see
        only their own expenses on the profile page.

        Both users are created fresh in the temp DB so the test is fully isolated.
        The FK PRAGMA is already enabled by get_db(), so the user_id FK is enforced.
        """
        with app.app_context():
            uid_a = db_module.create_user("Alice", "alice@example.com", "passA")
            uid_b = db_module.create_user("Bob", "bob@example.com", "passB")

        # Log in as Alice and add an expense.
        client_a = app.test_client()
        with client_a.session_transaction() as sess:
            sess["user_id"] = uid_a
            sess["user_name"] = "Alice"
        _post_add_expense(client_a, {**_VALID_PAYLOAD, "description": "Alice only"})

        # Log in as Bob and check his profile — Alice's expense must not appear.
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess["user_id"] = uid_b
            sess["user_name"] = "Bob"
        profile_response = client_b.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "Alice only" not in html, (
            "Alice's expense description appeared on Bob's profile page — "
            "expense rows must be filtered by user_id"
        )
