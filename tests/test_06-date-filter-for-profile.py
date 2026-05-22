# tests/test_06-date-filter-for-profile.py
# Tests for: Date Filter for Profile Page (/profile)
# Spec: .claude/specs/06-date-filter-for-profile.md
#
# This feature is entirely client-side (vanilla JS). Server-side tests confirm:
#   - The profile page renders the filter bar HTML elements
#   - Every expense <tr> carries a data-date="YYYY-MM-DD" attribute
#   - The no-results row exists and is hidden by default
#   - Authentication guard is enforced
#   - All four preset buttons are present with correct data-preset values
#   - The filter bar sits inside the transaction card (above the table)
#   - main.js is loaded via base.html
#
# DB isolation: monkeypatches database.db.DB_PATH to a tmp_path file so
# no test ever touches the committed spendly.db.

import importlib
import re

import pytest

from database import db as db_module


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Flask app wired to an isolated, throwaway SQLite file."""
    test_db = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db))

    # Reload app so the module-level init_db() / seed_db() block runs
    # against the patched DB_PATH, not the committed spendly.db.
    import app as app_module
    importlib.reload(app_module)
    flask_app = app_module.app
    flask_app.config.update({"TESTING": True})

    with flask_app.app_context():
        db_module.init_db()

    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded_app(app):
    """App with the standard 8-expense demo dataset loaded."""
    with app.app_context():
        db_module.seed_db()
    return app


@pytest.fixture()
def seeded_client(seeded_app):
    return seeded_app.test_client()


@pytest.fixture()
def logged_in_client(seeded_app):
    """Authenticated test client for the seeded demo user (id=1)."""
    client = seeded_app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Demo User"
    return client


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def get_profile_html(logged_in_client):
    """GET /profile and return the decoded response body."""
    response = logged_in_client.get("/profile")
    assert response.status_code == 200, (
        f"Expected 200 from /profile, got {response.status_code}"
    )
    return response.data.decode("utf-8")


# ------------------------------------------------------------------ #
# Test class                                                          #
# ------------------------------------------------------------------ #

class TestDateFilterProfilePage:

    # -------------------------------------------------------------- #
    # Authentication guard                                            #
    # -------------------------------------------------------------- #

    def test_profile_redirects_to_login_when_unauthenticated(self, seeded_client):
        """Unauthenticated GET /profile must redirect to /login."""
        response = seeded_client.get("/profile")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_profile_redirects_follow_lands_on_login_page(self, seeded_client):
        """Following the redirect from an unauthenticated /profile request
        should render the login page (200 with login form present)."""
        response = seeded_client.get("/profile", follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Login page should contain the email/password form inputs
        assert 'type="email"' in html or 'name="email"' in html

    # -------------------------------------------------------------- #
    # Filter inputs: id="filter-from" and id="filter-to"             #
    # -------------------------------------------------------------- #

    def test_filter_from_input_present(self, logged_in_client):
        """Profile page must render an <input> with id="filter-from"."""
        html = get_profile_html(logged_in_client)
        assert 'id="filter-from"' in html

    def test_filter_from_is_date_type(self, logged_in_client):
        """filter-from input must be type="date"."""
        html = get_profile_html(logged_in_client)
        # Find the input tag containing id="filter-from" and confirm type="date"
        match = re.search(r'<input[^>]*id="filter-from"[^>]*>', html)
        assert match is not None, '<input id="filter-from"> not found'
        tag = match.group(0)
        assert 'type="date"' in tag, f'Expected type="date" in: {tag}'

    def test_filter_to_input_present(self, logged_in_client):
        """Profile page must render an <input> with id="filter-to"."""
        html = get_profile_html(logged_in_client)
        assert 'id="filter-to"' in html

    def test_filter_to_is_date_type(self, logged_in_client):
        """filter-to input must be type="date"."""
        html = get_profile_html(logged_in_client)
        match = re.search(r'<input[^>]*id="filter-to"[^>]*>', html)
        assert match is not None, '<input id="filter-to"> not found'
        tag = match.group(0)
        assert 'type="date"' in tag, f'Expected type="date" in: {tag}'

    # -------------------------------------------------------------- #
    # Apply button                                                    #
    # -------------------------------------------------------------- #

    def test_filter_apply_button_present(self, logged_in_client):
        """Profile page must render a button with id="filter-apply"."""
        html = get_profile_html(logged_in_client)
        assert 'id="filter-apply"' in html

    def test_filter_apply_is_button_element(self, logged_in_client):
        """The filter-apply element must be a <button>."""
        html = get_profile_html(logged_in_client)
        match = re.search(r'<button[^>]*id="filter-apply"[^>]*>', html)
        assert match is not None, '<button id="filter-apply"> not found'

    # -------------------------------------------------------------- #
    # Preset buttons                                                  #
    # -------------------------------------------------------------- #

    def test_preset_all_time_button_present(self, logged_in_client):
        """Profile page must render a preset button with data-preset="all"
        and visible text "All Time"."""
        html = get_profile_html(logged_in_client)
        assert 'data-preset="all"' in html
        assert "All Time" in html

    def test_preset_this_month_button_present(self, logged_in_client):
        """Profile page must render a preset button with data-preset="month"
        and visible text "This Month"."""
        html = get_profile_html(logged_in_client)
        assert 'data-preset="month"' in html
        assert "This Month" in html

    def test_preset_last_3_months_button_present(self, logged_in_client):
        """Profile page must render a preset button with data-preset="3months"
        and visible text "Last 3 Months"."""
        html = get_profile_html(logged_in_client)
        assert 'data-preset="3months"' in html
        assert "Last 3 Months" in html

    def test_preset_last_6_months_button_present(self, logged_in_client):
        """Profile page must render a preset button with data-preset="6months"
        and visible text "Last 6 Months"."""
        html = get_profile_html(logged_in_client)
        assert 'data-preset="6months"' in html
        assert "Last 6 Months" in html

    def test_all_four_preset_buttons_are_present(self, logged_in_client):
        """All four preset buttons must be rendered in a single page load."""
        html = get_profile_html(logged_in_client)
        for preset_value in ("all", "month", "3months", "6months"):
            assert f'data-preset="{preset_value}"' in html, (
                f'Preset button data-preset="{preset_value}" not found in rendered HTML'
            )

    # -------------------------------------------------------------- #
    # data-date attributes on expense rows                            #
    # -------------------------------------------------------------- #

    def test_expense_rows_have_data_date_attribute(self, logged_in_client):
        """Every expense <tr> must have a data-date attribute."""
        html = get_profile_html(logged_in_client)
        # Collect all <tr> tags that contain data-date
        data_date_matches = re.findall(r'<tr[^>]*data-date="([^"]+)"[^>]*>', html)
        # The seeded dataset has 8 expenses
        assert len(data_date_matches) == 8, (
            f"Expected 8 expense rows with data-date, found {len(data_date_matches)}"
        )

    def test_data_date_values_are_iso8601(self, logged_in_client):
        """Every data-date value must match the YYYY-MM-DD ISO 8601 format."""
        html = get_profile_html(logged_in_client)
        data_date_values = re.findall(r'data-date="([^"]+)"', html)
        iso_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for value in data_date_values:
            assert iso_pattern.match(value), (
                f'data-date value "{value}" is not in YYYY-MM-DD format'
            )

    def test_data_date_values_match_seeded_dates(self, logged_in_client):
        """The data-date values rendered must exactly match the 8 seeded dates."""
        expected_dates = {
            "2026-05-01",
            "2026-05-03",
            "2026-05-05",
            "2026-05-08",
            "2026-05-10",
            "2026-05-13",
            "2026-05-15",
            "2026-05-18",
        }
        html = get_profile_html(logged_in_client)
        rendered_dates = set(re.findall(r'data-date="([^"]+)"', html))
        assert rendered_dates == expected_dates, (
            f"Rendered dates {rendered_dates} do not match expected {expected_dates}"
        )

    def test_data_date_is_on_tr_not_td(self, logged_in_client):
        """The data-date attribute must be on the <tr> element, not a <td>.
        JS row-hiding depends on this placement."""
        html = get_profile_html(logged_in_client)
        # Any <td> with data-date would be a placement bug
        td_with_data_date = re.findall(r'<td[^>]*data-date="[^"]*"[^>]*>', html)
        assert len(td_with_data_date) == 0, (
            "data-date found on <td> elements — must be on <tr> instead"
        )

    # -------------------------------------------------------------- #
    # No-results row                                                  #
    # -------------------------------------------------------------- #

    def test_no_results_row_is_present_in_html(self, logged_in_client):
        """The no-results row (id="no-results-row") must exist in the rendered HTML."""
        html = get_profile_html(logged_in_client)
        assert 'id="no-results-row"' in html

    def test_no_results_row_is_hidden_by_default(self, logged_in_client):
        """The no-results row must be hidden by default via style="display:none;"
        so it only appears when JS determines the filter produces zero visible rows."""
        html = get_profile_html(logged_in_client)
        # Locate the no-results-row <tr> tag and verify it carries display:none
        match = re.search(r'<tr[^>]*id="no-results-row"[^>]*>', html)
        assert match is not None, '<tr id="no-results-row"> not found'
        tag = match.group(0)
        assert "display:none" in tag or "display: none" in tag, (
            f'Expected style="display:none;" on no-results-row, got: {tag}'
        )

    def test_no_results_row_contains_expected_message(self, logged_in_client):
        """The no-results row must contain the spec-defined message text."""
        html = get_profile_html(logged_in_client)
        assert "No expenses match the selected dates." in html

    def test_no_results_row_spans_all_four_columns(self, logged_in_client):
        """The no-results row <td> must use colspan="4" to span the full table."""
        html = get_profile_html(logged_in_client)
        # Find the no-results-row and check its td has colspan=4
        # Locate from id="no-results-row" forward to the closing </tr>
        match = re.search(
            r'id="no-results-row".*?</tr>',
            html,
            re.DOTALL,
        )
        assert match is not None, "Could not locate no-results-row block"
        row_html = match.group(0)
        assert 'colspan="4"' in row_html, (
            "no-results-row <td> must have colspan=\"4\" to span Date, "
            "Description, Category, Amount columns"
        )

    # -------------------------------------------------------------- #
    # Filter bar placement — inside the transaction card              #
    # -------------------------------------------------------------- #

    def test_filter_bar_appears_before_expense_table(self, logged_in_client):
        """The filter bar must appear in the HTML before the expense table,
        confirming it sits above the table inside the transaction card."""
        html = get_profile_html(logged_in_client)
        filter_bar_pos = html.find('id="filter-from"')
        table_pos = html.find('<table')
        assert filter_bar_pos != -1, 'id="filter-from" not found'
        assert table_pos != -1, '<table> not found'
        assert filter_bar_pos < table_pos, (
            "Filter bar (filter-from input) must appear before the expense <table> "
            "in the HTML, but it was found after"
        )

    def test_filter_bar_and_table_are_in_same_card(self, logged_in_client):
        """The filter bar and the expense table must both be inside the same
        .profile-card container — confirmed by both appearing between one
        .profile-card opening div and its matching table close."""
        html = get_profile_html(logged_in_client)
        # Both filter-from and <table> must exist inside the transaction card block
        card_start = html.find('class="profile-card"', html.find("Recent Transactions"))
        assert card_start != -1, "Transaction .profile-card not found"
        card_content = html[card_start:]
        assert 'id="filter-from"' in card_content, (
            "filter-from not found inside the transaction profile-card"
        )
        assert "<table" in card_content, (
            "<table> not found inside the transaction profile-card"
        )

    # -------------------------------------------------------------- #
    # main.js script tag in base layout                               #
    # -------------------------------------------------------------- #

    def test_main_js_script_tag_present(self, logged_in_client):
        """The rendered profile page HTML must include a <script> tag
        that loads static/js/main.js (via base.html)."""
        html = get_profile_html(logged_in_client)
        assert "main.js" in html, (
            "main.js script tag not found in rendered HTML — "
            "base.html must include the main.js <script> tag"
        )

    def test_main_js_loaded_via_url_for(self, logged_in_client):
        """The main.js script must be loaded through Flask's static URL
        (i.e. /static/js/main.js), not a hardcoded relative path."""
        html = get_profile_html(logged_in_client)
        assert "/static/js/main.js" in html, (
            "Expected /static/js/main.js in rendered HTML "
            "(loaded via url_for in base.html)"
        )

    # -------------------------------------------------------------- #
    # Expense table structure integrity                               #
    # -------------------------------------------------------------- #

    def test_expense_table_has_four_columns(self, logged_in_client):
        """The expense table header must have exactly four columns:
        Date, Description, Category, Amount."""
        html = get_profile_html(logged_in_client)
        header_match = re.search(r'<thead>(.*?)</thead>', html, re.DOTALL)
        assert header_match is not None, "<thead> not found"
        thead_html = header_match.group(1)
        th_tags = re.findall(r'<th[^>]*>', thead_html)
        assert len(th_tags) == 4, (
            f"Expected 4 <th> columns, found {len(th_tags)}"
        )

    def test_expense_table_column_headers(self, logged_in_client):
        """Expense table must have Date, Description, Category, Amount headers."""
        html = get_profile_html(logged_in_client)
        for header in ("Date", "Description", "Category", "Amount"):
            assert header in html, f'Column header "{header}" not found in rendered HTML'

    def test_expense_amounts_use_rupee_symbol(self, logged_in_client):
        """All expense amounts in the table must be prefixed with ₹
        (Indian Rupee), never £ or $."""
        html = get_profile_html(logged_in_client)
        assert "₹" in html, "Rupee symbol ₹ not found in profile page"
        assert "£" not in html, "Found £ (GBP) — amounts must use ₹"
        assert "$" not in html, "Found $ (USD) — amounts must use ₹"

    # -------------------------------------------------------------- #
    # Profile page stats section unaffected                          #
    # -------------------------------------------------------------- #

    def test_stats_section_still_renders_with_filter_bar(self, logged_in_client):
        """Adding the filter bar must not break the stats section.
        Total Spent, Transactions, and Top Category cards must still render."""
        html = get_profile_html(logged_in_client)
        assert "Total Spent" in html
        assert "Transactions" in html
        assert "Top Category" in html

    def test_total_spent_value_correct_for_seeded_data(self, logged_in_client):
        """Stats card must show the correct total for the 8 seeded expenses: ₹329.89."""
        html = get_profile_html(logged_in_client)
        assert "329.89" in html, (
            "Expected total_spent of 329.89 for seeded data "
            "(12.50+45.00+120.00+35.00+18.99+67.40+9.00+22.00)"
        )

    def test_transaction_count_correct_for_seeded_data(self, logged_in_client):
        """Stats card must show transaction_count = 8 for the seeded dataset."""
        html = get_profile_html(logged_in_client)
        assert ">8<" in html or "8</span>" in html or ">8 <" in html or "8\n" in html, (
            "Expected transaction_count of 8 in rendered HTML"
        )

    def test_top_category_is_bills_for_seeded_data(self, logged_in_client):
        """Stats card must show top_category = Bills (₹120.00, highest single category)."""
        html = get_profile_html(logged_in_client)
        assert "Bills" in html, "Expected Bills as top_category for seeded data"
