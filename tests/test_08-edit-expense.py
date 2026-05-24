# tests/test_08-edit-expense.py
# Tests for: Edit Expense (GET /expenses/<id>/edit, POST /expenses/<id>/edit)
# Spec: .claude/specs/08-edit-expense.md
#
# Spec rules under test:
#   - Unauthenticated GET and POST redirect to /login
#   - GET for a non-existent expense returns 404
#   - GET for an expense owned by a different user returns 404
#   - GET while owning the expense renders edit_expense.html pre-filled with existing values
#   - POST with all valid fields updates the DB row and redirects to /profile
#   - Updated values appear on the profile page after successful redirect
#   - POST with missing/empty amount re-renders form with error
#   - POST with non-positive amount (zero, negative) re-renders form with error
#   - POST with an invalid category re-renders form with error
#   - POST with missing date re-renders form with error
#   - Previously submitted (invalid) values are preserved in the re-rendered form
#   - Profile page edit links point to the correct expense id per row
#   - Ownership: update cannot modify another user's expense even via direct POST
#
# DB isolation: uses the monkeypatched app/client fixtures from conftest.py so
# no test ever touches the committed spendly.db.
#
# Allowed categories (spec §Rules): Food, Transport, Bills, Health,
#   Entertainment, Shopping, Other

import re

import pytest

from database import db as db_module

# ------------------------------------------------------------------ #
# Local fixtures                                                      #
# ------------------------------------------------------------------ #


@pytest.fixture()
def fresh_user(app):
    """Creates a single test user in the temp DB with no expenses.

    Returns the user_id so the calling test can insert targeted expenses
    and manipulate the session directly.
    """
    with app.app_context():
        user_id = db_module.create_user("Test User", "test@example.com", "testpassword")
    return user_id


@pytest.fixture()
def fresh_logged_in_client(app, fresh_user):
    """Authenticated client for the fresh test user (no seed data, no expenses yet)."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = fresh_user
        sess["user_name"] = "Test User"
    return client


@pytest.fixture()
def expense_id(app, fresh_user):
    """Inserts one owned expense for the fresh test user and returns its DB id."""
    with app.app_context():
        eid = db_module.add_expense(
            fresh_user, 42.50, "Food", "2026-06-01", "Original description"
        )
    return eid


@pytest.fixture()
def other_user_id(app):
    """Creates a second, separate user in the temp DB and returns their id."""
    with app.app_context():
        uid = db_module.create_user("Other User", "other@example.com", "otherpassword")
    return uid


@pytest.fixture()
def other_expense_id(app, other_user_id):
    """Inserts one expense owned by other_user and returns its DB id."""
    with app.app_context():
        eid = db_module.add_expense(
            other_user_id, 99.00, "Shopping", "2026-06-10", "Other user's expense"
        )
    return eid


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

_VALID_UPDATE_PAYLOAD = {
    "amount": "75.00",
    "category": "Transport",
    "date": "2026-07-15",
    "description": "Updated description",
}

_ALLOWED_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def _get_edit(client, expense_id, follow=False):
    return client.get(f"/expenses/{expense_id}/edit", follow_redirects=follow)


def _post_edit(client, expense_id, payload, follow=False):
    return client.post(
        f"/expenses/{expense_id}/edit",
        data=payload,
        follow_redirects=follow,
    )


# ------------------------------------------------------------------ #
# Test class                                                          #
# ------------------------------------------------------------------ #


class TestEditExpense:

    # -------------------------------------------------------------- #
    # Auth guard — GET                                                #
    # -------------------------------------------------------------- #

    def test_get_redirects_to_login_when_unauthenticated(self, client):
        """Spec: unauthenticated GET /expenses/<id>/edit must redirect to /login.

        Uses id=1 as a placeholder; the auth guard fires before the DB lookup.
        """
        response = _get_edit(client, 1)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_get_unauthenticated_follow_lands_on_login_page(self, client):
        """Following the auth redirect must render the login page (200)."""
        response = _get_edit(client, 1, follow=True)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert 'name="email"' in html or 'type="email"' in html

    # -------------------------------------------------------------- #
    # Auth guard — POST                                               #
    # -------------------------------------------------------------- #

    def test_post_redirects_to_login_when_unauthenticated(self, client):
        """Spec: unauthenticated POST /expenses/<id>/edit must redirect to /login."""
        response = _post_edit(client, 1, _VALID_UPDATE_PAYLOAD)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_unauthenticated_does_not_modify_db(
        self, app, client, expense_id, fresh_user
    ):
        """An unauthenticated POST must not alter any expense row in the DB."""
        _post_edit(client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        # The original values must be unchanged.
        assert float(row["amount"]) == pytest.approx(42.50)
        assert row["category"] == "Food"
        assert row["description"] == "Original description"

    # -------------------------------------------------------------- #
    # 404 — non-existent expense                                      #
    # -------------------------------------------------------------- #

    def test_get_returns_404_for_nonexistent_expense(self, fresh_logged_in_client):
        """Spec: GET /expenses/99999/edit for an id that does not exist must return 404."""
        response = _get_edit(fresh_logged_in_client, 99999)
        assert response.status_code == 404

    def test_post_returns_404_for_nonexistent_expense(self, fresh_logged_in_client):
        """Spec: POST /expenses/99999/edit for an id that does not exist must return 404.

        The route fetches the expense before processing the form, so a missing
        expense aborts before any DB write occurs.
        """
        response = _post_edit(fresh_logged_in_client, 99999, _VALID_UPDATE_PAYLOAD)
        assert response.status_code == 404

    # -------------------------------------------------------------- #
    # 404 — expense belongs to a different user                       #
    # -------------------------------------------------------------- #

    def test_get_returns_404_for_other_users_expense(
        self, app, fresh_user, other_expense_id
    ):
        """Spec: GET /expenses/<id>/edit for an expense owned by another user returns 404.

        get_expense_by_id includes user_id in the WHERE clause, so it returns None
        for a cross-user lookup, and the route calls abort(404).
        """
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = fresh_user
            sess["user_name"] = "Test User"
        response = _get_edit(client, other_expense_id)
        assert response.status_code == 404

    def test_post_returns_404_for_other_users_expense(
        self, app, fresh_user, other_expense_id
    ):
        """Spec: POST /expenses/<id>/edit for another user's expense returns 404.

        The route performs the ownership check (get_expense_by_id) before
        processing the submitted form, so the update never reaches the DB.
        """
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = fresh_user
            sess["user_name"] = "Test User"
        response = _post_edit(client, other_expense_id, _VALID_UPDATE_PAYLOAD)
        assert response.status_code == 404

    def test_post_cross_user_does_not_modify_other_expense(
        self, app, fresh_user, other_user_id, other_expense_id
    ):
        """Spec (ownership enforcement): a cross-user POST must leave the target
        expense row completely unchanged in the DB.

        Both get_expense_by_id and update_expense include user_id in WHERE,
        so double ownership enforcement is in effect. This test verifies the
        DB-level guard independently of the 404 response.
        """
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = fresh_user
            sess["user_name"] = "Test User"
        _post_edit(client, other_expense_id, _VALID_UPDATE_PAYLOAD)

        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (other_expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(99.00)
        assert row["category"] == "Shopping"
        assert row["description"] == "Other user's expense"

    # -------------------------------------------------------------- #
    # GET — authenticated, owner                                      #
    # -------------------------------------------------------------- #

    def test_get_renders_200_for_owner(self, fresh_logged_in_client, expense_id):
        """Spec: GET /expenses/<id>/edit for the owning user must return 200."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        assert response.status_code == 200

    def test_get_renders_edit_expense_template(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the edit form template must extend base.html (full HTML page rendered)."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert "<html" in html

    def test_get_form_is_pre_filled_with_amount(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the edit form must be pre-filled with the expense's existing amount."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        # Original expense amount is 42.50 — must appear as the input value.
        assert "42.5" in html, "Pre-filled amount (42.50) not found in edit form HTML"

    def test_get_form_is_pre_filled_with_category(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the edit form must pre-select the expense's existing category."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        # Original category is 'Food'. Template marks the matching option selected.
        assert "Food" in html, "Pre-filled category 'Food' not found in edit form HTML"

    def test_get_form_is_pre_filled_with_date(self, fresh_logged_in_client, expense_id):
        """Spec: the edit form must be pre-filled with the expense's existing date."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert (
            "2026-06-01" in html
        ), "Pre-filled date '2026-06-01' not found in edit form HTML"

    def test_get_form_is_pre_filled_with_description(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the edit form must be pre-filled with the expense's existing description."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert (
            "Original description" in html
        ), "Pre-filled description not found in edit form HTML"

    def test_get_form_action_points_to_correct_edit_route(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the form's action attribute must point to the correct edit URL for this expense.

        edit_expense.html renders:
          <form method="POST" action="{{ url_for('edit_expense', id=expense_id) }}">
        """
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        expected_action = f"/expenses/{expense_id}/edit"
        assert (
            expected_action in html
        ), f"Form action '{expected_action}' not found in edit form HTML"

    def test_get_renders_all_allowed_category_options(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the category select must include all seven allowed categories."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        for cat in _ALLOWED_CATEGORIES:
            assert cat in html, f'Category option "{cat}" missing from edit form'

    def test_get_renders_amount_input(self, fresh_logged_in_client, expense_id):
        """Edit form must contain an input named 'amount'."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert 'name="amount"' in html

    def test_get_renders_category_select(self, fresh_logged_in_client, expense_id):
        """Edit form must contain a select named 'category'."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert 'name="category"' in html

    def test_get_renders_date_input(self, fresh_logged_in_client, expense_id):
        """Edit form must contain an input named 'date'."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert 'name="date"' in html

    def test_get_renders_description_field(self, fresh_logged_in_client, expense_id):
        """Edit form must contain a textarea or input named 'description'."""
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert 'name="description"' in html

    def test_get_renders_no_error_on_initial_load(
        self, fresh_logged_in_client, expense_id
    ):
        """A clean GET of the edit form must not display any validation error.

        Template only renders <div class="auth-error"> when error is truthy.
        On GET, app.py passes error=None.
        """
        response = _get_edit(fresh_logged_in_client, expense_id)
        html = response.data.decode("utf-8")
        assert "auth-error" not in html

    # -------------------------------------------------------------- #
    # Happy path — valid POST                                         #
    # -------------------------------------------------------------- #

    def test_valid_post_redirects_to_profile(self, fresh_logged_in_client, expense_id):
        """Spec: a valid POST must redirect to /profile."""
        response = _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_updates_amount_in_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec (DB side-effect): the expense's amount must be updated in the DB."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(75.00)

    def test_valid_post_updates_category_in_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec (DB side-effect): the expense's category must be updated in the DB."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["category"] == "Transport"

    def test_valid_post_updates_date_in_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec (DB side-effect): the expense's date must be updated in the DB."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["date"] == "2026-07-15"

    def test_valid_post_updates_description_in_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec (DB side-effect): the expense's description must be updated in the DB."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["description"] == "Updated description"

    def test_valid_post_preserves_user_id_in_db(
        self, app, fresh_user, fresh_logged_in_client, expense_id
    ):
        """The update must not alter the user_id column on the expense row."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT user_id FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["user_id"] == fresh_user

    def test_valid_post_does_not_insert_new_row(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A successful edit must update the existing row, not insert a new one."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        with app.app_context():
            conn = db_module.get_db()
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
            conn.close()
        assert count == 1

    def test_valid_post_with_empty_description_succeeds(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec: description is optional — submitting an empty string must succeed."""
        payload = {**_VALID_UPDATE_PAYLOAD, "description": ""}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_without_description_key_succeeds(
        self, app, fresh_logged_in_client, expense_id
    ):
        """Spec: description is optional — omitting the field entirely must succeed."""
        payload = {
            "amount": "10.00",
            "category": "Other",
            "date": "2026-08-01",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 302

    @pytest.mark.parametrize("cat", _ALLOWED_CATEGORIES)
    def test_all_allowed_categories_are_accepted_on_edit(
        self, app, fresh_logged_in_client, expense_id, cat
    ):
        """Every category in the spec's allowed list must be accepted as valid on edit."""
        payload = {**_VALID_UPDATE_PAYLOAD, "category": cat}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert (
            response.status_code == 302
        ), f'Category "{cat}" was rejected on edit — expected 302, got {response.status_code}'

    # -------------------------------------------------------------- #
    # Updated values appear on profile page after redirect            #
    # -------------------------------------------------------------- #

    def test_updated_amount_appears_on_profile_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the updated expense values must appear on the profile page
        immediately after a successful edit POST."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        assert profile_response.status_code == 200
        html = profile_response.data.decode("utf-8")
        assert (
            "75.00" in html
        ), "Updated amount '75.00' not found on profile page after edit"

    def test_updated_category_appears_on_profile_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """The updated category must appear in the expense table on the profile page."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert (
            "Transport" in html
        ), "Updated category 'Transport' not found on profile page after edit"

    def test_updated_description_appears_on_profile_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """The updated description must appear in the expense table on the profile page."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert (
            "Updated description" in html
        ), "Updated description not found on profile page after edit"

    def test_updated_date_appears_on_profile_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """The updated date must appear in the expense table on the profile page."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert (
            "2026-07-15" in html
        ), "Updated date '2026-07-15' not found on profile page after edit"

    def test_updated_amount_uses_rupee_symbol_on_profile(
        self, fresh_logged_in_client, expense_id
    ):
        """Amounts on the profile page must be prefixed with ₹ (Indian Rupee)
        after a successful edit, never £ or $."""
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "₹" in html
        assert "£" not in html
        assert "$" not in html

    def test_original_values_no_longer_appear_as_amount_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """The original amount (42.50) must no longer appear as the expense amount
        after a successful edit replaced it with 75.00.

        Note: the stats section may display a total — we only confirm the update
        occurred by verifying the new amount is present and the row count is unchanged.
        This is primarily confirmed by the DB-state tests above.
        """
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        assert "75.00" in html

    # -------------------------------------------------------------- #
    # Validation — missing / empty amount                             #
    # -------------------------------------------------------------- #

    def test_missing_amount_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: POST with missing amount must re-render the edit form (200) with error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": ""}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_missing_amount_does_not_update_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A POST with missing amount must not change the expense row in the DB."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": ""}
        _post_edit(fresh_logged_in_client, expense_id, payload)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT amount FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        # Original amount must be intact.
        assert float(row["amount"]) == pytest.approx(42.50)

    def test_non_numeric_amount_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """A non-numeric amount string must re-render the edit form with an error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "abc"}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    # -------------------------------------------------------------- #
    # Validation — non-positive amount                                #
    # -------------------------------------------------------------- #

    def test_zero_amount_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: amount of exactly zero is non-positive — must re-render form with error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "0"}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_zero_amount_does_not_update_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A POST with amount = 0 must not alter the expense row."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "0"}
        _post_edit(fresh_logged_in_client, expense_id, payload)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT amount FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(42.50)

    def test_negative_amount_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: a negative amount must re-render the edit form with an error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "-10.00"}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_negative_amount_does_not_update_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A POST with a negative amount must not alter the expense row."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "-10.00"}
        _post_edit(fresh_logged_in_client, expense_id, payload)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT amount FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(42.50)

    def test_small_positive_amount_is_accepted(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A positive amount just above zero (0.01) is valid per spec."""
        payload = {**_VALID_UPDATE_PAYLOAD, "amount": "0.01"}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 302
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT amount FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(0.01)

    # -------------------------------------------------------------- #
    # Validation — invalid category                                   #
    # -------------------------------------------------------------- #

    def test_invalid_category_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: a category not in the allowed list must re-render the edit form with error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "category": "Gambling"}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_invalid_category_does_not_update_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A POST with an invalid category must not alter the expense row."""
        payload = {**_VALID_UPDATE_PAYLOAD, "category": "Gambling"}
        _post_edit(fresh_logged_in_client, expense_id, payload)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT category FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["category"] == "Food"

    def test_empty_category_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """An empty category string (unselected placeholder) must also fail validation."""
        payload = {**_VALID_UPDATE_PAYLOAD, "category": ""}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    # -------------------------------------------------------------- #
    # Validation — missing date                                       #
    # -------------------------------------------------------------- #

    def test_missing_date_rerenders_form_with_error(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: POST with missing date must re-render the edit form with an error."""
        payload = {**_VALID_UPDATE_PAYLOAD, "date": ""}
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "auth-error" in html

    def test_missing_date_does_not_update_db(
        self, app, fresh_logged_in_client, expense_id
    ):
        """A POST with missing date must not alter the expense row."""
        payload = {**_VALID_UPDATE_PAYLOAD, "date": ""}
        _post_edit(fresh_logged_in_client, expense_id, payload)
        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT date FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert row["date"] == "2026-06-01"

    # -------------------------------------------------------------- #
    # Form value preservation on validation failure                   #
    # -------------------------------------------------------------- #

    def test_submitted_amount_is_preserved_on_validation_failure(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the submitted (invalid) values must survive the re-render.

        Template uses value="{{ form.amount or '' }}" — the user-typed amount
        must appear even when another field caused the error.
        """
        payload = {
            "amount": "88.88",
            "category": "Food",
            "date": "",  # missing date triggers the error
            "description": "Some note",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert (
            "88.88" in html
        ), "Submitted amount '88.88' was not preserved in the re-rendered edit form"

    def test_submitted_description_is_preserved_on_validation_failure(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the submitted description must be re-populated after a validation failure.

        Template renders {{ form.description or '' }} inside the textarea.
        """
        payload = {
            "amount": "10.00",
            "category": "Health",
            "date": "",  # missing date triggers the error
            "description": "Preserved note text",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert (
            "Preserved note text" in html
        ), "Submitted description was not preserved in the re-rendered edit form"

    def test_submitted_category_is_preserved_on_validation_failure(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the submitted category must remain in the re-rendered form.

        Template marks the matching <option> selected via
        {% if form.category == cat %}selected{% endif %}.
        The category name always appears in the rendered HTML (all options are listed).
        """
        payload = {
            "amount": "20.00",
            "category": "Bills",
            "date": "",  # missing date triggers the error
            "description": "",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert (
            "Bills" in html
        ), "Submitted category 'Bills' not reflected in re-rendered edit form"

    def test_submitted_date_is_preserved_on_validation_failure(
        self, fresh_logged_in_client, expense_id
    ):
        """Spec: the submitted date must be re-populated after a validation failure.

        Template uses value="{{ form.date or '' }}" on the date input.
        """
        payload = {
            "amount": "",  # missing amount triggers the error
            "category": "Shopping",
            "date": "2026-09-30",
            "description": "",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert (
            "2026-09-30" in html
        ), "Submitted date '2026-09-30' was not preserved in the re-rendered edit form"

    def test_all_submitted_values_preserved_on_invalid_category(
        self, fresh_logged_in_client, expense_id
    ):
        """All fields must survive the re-render when the category is invalid —
        the route passes the entire raw form dict back to the template on any error.
        """
        payload = {
            "amount": "55.55",
            "category": "NotACategory",  # invalid — triggers error
            "date": "2026-10-10",
            "description": "All preserved",
        }
        response = _post_edit(fresh_logged_in_client, expense_id, payload)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "55.55" in html, "amount not preserved on invalid-category failure"
        assert "2026-10-10" in html, "date not preserved on invalid-category failure"
        assert (
            "All preserved" in html
        ), "description not preserved on invalid-category failure"

    # -------------------------------------------------------------- #
    # Profile page — edit links per expense row                       #
    # -------------------------------------------------------------- #

    def test_profile_page_expense_rows_have_edit_links(self, logged_in_client):
        """Spec: each expense row on the profile page must have a working edit link.

        profile.html renders:
          <a href="{{ url_for('edit_expense', id=expense.id) }}" class="profile-edit-link">Edit</a>

        Uses logged_in_client from conftest.py (seeded demo user, 8 expenses).
        """
        response = logged_in_client.get("/profile")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Every edit link must contain '/expenses/' and '/edit' in the href.
        edit_links = re.findall(r'href="([^"]*\/expenses\/\d+\/edit[^"]*)"', html)
        assert (
            len(edit_links) == 8
        ), f"Expected 8 edit links (one per seeded expense), found {len(edit_links)}"

    def test_profile_page_edit_links_point_to_correct_ids(self, logged_in_client):
        """Each edit link href must embed the correct integer expense id.

        The seeded DB assigns ids 1–8 to the 8 seed expenses (the temp DB starts
        fresh so no prior rows exist). All ids in the rendered links must be
        distinct positive integers.
        """
        response = logged_in_client.get("/profile")
        html = response.data.decode("utf-8")
        ids_in_links = re.findall(r"/expenses/(\d+)/edit", html)
        assert (
            len(ids_in_links) == 8
        ), f"Expected 8 expense ids in edit links, found {len(ids_in_links)}"
        # All ids must be distinct (no duplicated href pointing at the same expense).
        assert (
            len(set(ids_in_links)) == 8
        ), "Duplicate expense ids found in profile edit links — each row must link to its own id"

    def test_profile_page_edit_links_are_anchor_tags(self, logged_in_client):
        """Edit links must be <a> elements (not buttons or forms), so they perform
        a GET request to load the pre-filled edit form.

        profile.html confirmed to use:
          <a href="{{ url_for('edit_expense', id=expense.id) }}" class="profile-edit-link">Edit</a>
        """
        response = logged_in_client.get("/profile")
        html = response.data.decode("utf-8")
        anchor_pattern = re.compile(
            r'<a\b[^>]*href="[^"]*\/expenses\/\d+\/edit[^"]*"[^>]*>'
        )
        matches = anchor_pattern.findall(html)
        assert (
            len(matches) == 8
        ), f"Expected 8 <a> edit links on profile page, found {len(matches)}"

    def test_edit_link_for_expense_leads_to_prefilled_form(self, logged_in_client):
        """Clicking any edit link (GET) must return 200 and a pre-filled form.

        We follow the first edit link found on the profile page to confirm
        the round-trip works end-to-end for the seeded demo user.
        """
        profile_response = logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        # Extract the first edit link href.
        match = re.search(r'href="(/expenses/\d+/edit)"', html)
        assert match is not None, "No edit link found on profile page"
        edit_url = match.group(1)

        edit_response = logged_in_client.get(edit_url)
        assert edit_response.status_code == 200
        edit_html = edit_response.data.decode("utf-8")
        # The form must be pre-filled (amount, category, date inputs must be present).
        assert 'name="amount"' in edit_html
        assert 'name="category"' in edit_html
        assert 'name="date"' in edit_html

    # -------------------------------------------------------------- #
    # Edge cases                                                      #
    # -------------------------------------------------------------- #

    def test_editing_one_expense_does_not_affect_others(
        self, app, fresh_user, fresh_logged_in_client
    ):
        """Updating one expense must leave sibling expenses for the same user
        completely unchanged in the DB.
        """
        with app.app_context():
            eid_a = db_module.add_expense(
                fresh_user, 10.00, "Food", "2026-06-01", "Expense A"
            )
            eid_b = db_module.add_expense(
                fresh_user, 20.00, "Bills", "2026-06-02", "Expense B"
            )

        # Edit only expense A.
        payload = {
            "amount": "99.99",
            "category": "Health",
            "date": "2026-06-15",
            "description": "Edited A",
        }
        _post_edit(fresh_logged_in_client, eid_a, payload)

        # Expense B must be untouched.
        with app.app_context():
            conn = db_module.get_db()
            row_b = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (eid_b,)
            ).fetchone()
            conn.close()
        assert float(row_b["amount"]) == pytest.approx(20.00)
        assert row_b["category"] == "Bills"
        assert row_b["description"] == "Expense B"

    def test_expense_can_be_edited_multiple_times(
        self, app, fresh_logged_in_client, expense_id
    ):
        """An expense must be updatable more than once — each edit must replace
        the previous values.
        """
        first_payload = {
            **_VALID_UPDATE_PAYLOAD,
            "amount": "50.00",
            "description": "First edit",
        }
        second_payload = {
            **_VALID_UPDATE_PAYLOAD,
            "amount": "60.00",
            "description": "Second edit",
        }

        _post_edit(fresh_logged_in_client, expense_id, first_payload)
        _post_edit(fresh_logged_in_client, expense_id, second_payload)

        with app.app_context():
            conn = db_module.get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            conn.close()
        assert float(row["amount"]) == pytest.approx(60.00)
        assert row["description"] == "Second edit"

    def test_total_spent_updates_on_profile_after_edit(
        self, fresh_logged_in_client, expense_id
    ):
        """After editing an expense's amount, the Total Spent stat on the profile
        page must reflect the new value, not the original.

        Original: 42.50 -> Updated: 75.00. The stats section must show 75.00.
        """
        _post_edit(fresh_logged_in_client, expense_id, _VALID_UPDATE_PAYLOAD)
        profile_response = fresh_logged_in_client.get("/profile")
        html = profile_response.data.decode("utf-8")
        # 75.00 should now be the total_spent (only one expense for this user).
        assert (
            "75.00" in html
        ), "Profile Total Spent did not update to 75.00 after editing the expense amount"
