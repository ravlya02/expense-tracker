import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"


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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "May 2026",
    }
    stats = {
        "total_spent": "329.89",
        "transaction_count": 8,
        "top_category": "Bills",
    }
    expenses = [
        {"date": "2026-05-18", "description": "Dinner with friends",    "category": "Food",          "amount": "22.00"},
        {"date": "2026-05-15", "description": "Stationery",             "category": "Other",         "amount": "9.00"},
        {"date": "2026-05-13", "description": "New headphones",         "category": "Shopping",      "amount": "67.40"},
        {"date": "2026-05-10", "description": "Streaming subscription", "category": "Entertainment", "amount": "18.99"},
        {"date": "2026-05-08", "description": "Pharmacy — vitamins",    "category": "Health",        "amount": "35.00"},
        {"date": "2026-05-05", "description": "Electricity bill",       "category": "Bills",         "amount": "120.00"},
        {"date": "2026-05-03", "description": "Monthly bus pass top-up","category": "Transport",     "amount": "45.00"},
        {"date": "2026-05-01", "description": "Lunch at the deli",      "category": "Food",          "amount": "12.50"},
    ]
    categories = [
        {"name": "Bills",         "amount": "120.00", "percent": 36},
        {"name": "Shopping",      "amount": "67.40",  "percent": 20},
        {"name": "Transport",     "amount": "45.00",  "percent": 14},
        {"name": "Health",        "amount": "35.00",  "percent": 11},
        {"name": "Food",          "amount": "34.50",  "percent": 10},
        {"name": "Entertainment", "amount": "18.99",  "percent": 6},
        {"name": "Other",         "amount": "9.00",   "percent": 3},
    ]
    return render_template("profile.html", user=user, stats=stats, expenses=expenses, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# ------------------------------------------------------------------ #
# Database initialisation                                             #
# ------------------------------------------------------------------ #
with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
