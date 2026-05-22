import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spendly.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def create_user(name, email, password):
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def seed_db():
    conn = get_db()

    row_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if row_count > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cur.lastrowid

    expenses = [
        (user_id, 12.50,  "Food",          "2026-05-01", "Lunch at the deli"),
        (user_id, 45.00,  "Transport",     "2026-05-03", "Monthly bus pass top-up"),
        (user_id, 120.00, "Bills",         "2026-05-05", "Electricity bill"),
        (user_id, 35.00,  "Health",        "2026-05-08", "Pharmacy — vitamins"),
        (user_id, 18.99,  "Entertainment", "2026-05-10", "Streaming subscription"),
        (user_id, 67.40,  "Shopping",      "2026-05-13", "New headphones"),
        (user_id, 9.00,   "Other",         "2026-05-15", "Stationery"),
        (user_id, 22.00,  "Food",          "2026-05-18", "Dinner with friends"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def get_expenses_by_user(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount "
            "FROM expenses WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": f"{row['amount']:.2f}",
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_expense_stats(user_id):
    conn = get_db()
    try:
        agg = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        total = agg["total"]
        count = agg["cnt"]

        cat_rows = conn.execute(
            "SELECT category, SUM(amount) AS cat_total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY cat_total DESC",
            (user_id,),
        ).fetchall()

        top_category = cat_rows[0]["category"] if cat_rows else "—"

        categories = []
        if total > 0:
            for row in cat_rows:
                categories.append({
                    "name": row["category"],
                    "amount": f"{row['cat_total']:.2f}",
                    "percent": round(row["cat_total"] / total * 100),
                })

        return {
            "total_spent": f"{total:.2f}",
            "transaction_count": count,
            "top_category": top_category,
            "categories": categories,
        }
    finally:
        conn.close()
