import os
import sqlite3
from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from database.db import (
    add_expense as db_add_expense,
    create_user,
    delete_expense as db_delete_expense,
    get_db,
    get_expense_by_id,
    get_expense_stats,
    get_expenses_by_user,
    get_user_by_id,
    get_user_by_email,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret")


ALLOWED_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def _validate_expense_form(amount_raw, category, date):
    """Returns (amount_or_None, error_or_None) for expense form submissions."""
    error = None
    amount = None
    try:
        amount = float(amount_raw)
        if amount <= 0:
            error = "Amount must be greater than zero."
    except ValueError:
        error = "Amount must be a valid number."

    if not error and category not in ALLOWED_CATEGORIES:
        error = "Please select a valid category."

    if not error and not date:
        error = "Date is required."
    elif not error:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            error = "Date must be in YYYY-MM-DD format."

    return amount, error


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="An account with that email already exists.",
            )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("profile"))
        return render_template("login.html", error="Invalid email or password.")
    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db_user = get_user_by_id(session["user_id"])
    if db_user is None:
        abort(404)
    from datetime import datetime

    created = datetime.strptime(db_user["created_at"][:10], "%Y-%m-%d")
    user = {
        "name": db_user["name"],
        "email": db_user["email"],
        "member_since": created.strftime("%B %Y"),
    }
    expense_stats = get_expense_stats(session["user_id"])
    stats = {
        "total_spent": expense_stats["total_spent"],
        "transaction_count": expense_stats["transaction_count"],
        "top_category": expense_stats["top_category"],
    }
    expenses = get_expenses_by_user(session["user_id"])
    categories = expense_stats["categories"]
    return render_template(
        "profile.html", user=user, stats=stats, expenses=expenses, categories=categories
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip() or None

        form = {
            "amount": amount_raw,
            "category": category,
            "date": date,
            "description": description or "",
        }

        amount, error = _validate_expense_form(amount_raw, category, date)

        if error or amount is None:
            return render_template(
                "add_expense.html",
                error=error,
                form=form,
                categories=ALLOWED_CATEGORIES,
            )

        db_add_expense(session["user_id"], amount, category, date, description)
        return redirect(url_for("profile"))

    return render_template(
        "add_expense.html",
        error=None,
        form={},
        categories=ALLOWED_CATEGORIES,
    )


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(expense_id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip() or None

        form = {
            "amount": amount_raw,
            "category": category,
            "date": date,
            "description": description or "",
        }

        amount, error = _validate_expense_form(amount_raw, category, date)

        if error or amount is None:
            return render_template(
                "edit_expense.html",
                error=error,
                form=form,
                categories=ALLOWED_CATEGORIES,
                expense_id=expense_id,
            )

        rows_updated = update_expense(
            expense_id, session["user_id"], amount, category, date, description
        )
        if not rows_updated:
            abort(404)
        return redirect(url_for("profile"))

    form = {
        "amount": expense["amount"],
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    return render_template(
        "edit_expense.html",
        error=None,
        form=form,
        categories=ALLOWED_CATEGORIES,
        expense_id=expense_id,
    )


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    expense = get_expense_by_id(expense_id, session["user_id"])
    if expense is None:
        abort(404)
    rows_deleted = db_delete_expense(expense_id, session["user_id"])
    if not rows_deleted:
        abort(404)
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Database initialisation                                             #
# ------------------------------------------------------------------ #
with app.app_context():
    init_db()


if __name__ == "__main__":
    seed_db()
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5002)
