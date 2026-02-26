import os
import sqlite3
from functools import wraps
from flask import Flask, g, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
@app.route("/")
def home():
    return {"status": "Journal API running"}
app.config["DATABASE"] = os.getenv("JOURNAL_DB_PATH", "/tmp/journal.db")
app.config["WRITE_API_KEY"] = os.getenv("WRITE_API_KEY", "change-me")

CORS(app)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            subject TEXT NOT NULL,
            to_name TEXT NOT NULL,
            from_name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    count = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    if count == 0:
        db.executemany(
            """
            INSERT INTO entries (entry_date, subject, to_name, from_name, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("2026-02-26", "today felt strange", "future me", "present me", "the day moved like static."),
                ("2026-02-24", "tired but okay", "sister", "me", "slept late again."),
            ],
        )

    db.commit()
    db.close()


def serialize_entry(row):
    return {
        "id": row["id"],
        "entry_date": row["entry_date"],
        "subject": row["subject"],
        "to_name": row["to_name"],
        "from_name": row["from_name"],
        "body": row["body"],
    }


def require_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if provided_key != app.config["WRITE_API_KEY"]:
            return jsonify({"error": "unauthorized"}), 401
        return func(*args, **kwargs)

    return wrapper


@app.route("/api/entries", methods=["GET"])
def list_entries():
    rows = get_db().execute(
        """
        SELECT id, entry_date, subject, to_name, from_name, body
        FROM entries
        ORDER BY entry_date DESC, id DESC
        """
    ).fetchall()
    return jsonify([serialize_entry(row) for row in rows])


@app.route("/api/entries/<int:entry_id>", methods=["GET"])
def get_entry(entry_id):
    row = get_db().execute(
        """
        SELECT id, entry_date, subject, to_name, from_name, body
        FROM entries
        WHERE id = ?
        """,
        (entry_id,),
    ).fetchone()

    if row is None:
        return jsonify({"error": "entry not found"}), 404

    return jsonify(serialize_entry(row))


@app.route("/api/search", methods=["GET"])
def search_entries():
    date_query = request.args.get("date", "").strip()
    keyword_query = request.args.get("keyword", "").strip()

    sql = """
        SELECT id, entry_date, subject, to_name, from_name, body
        FROM entries
        WHERE 1 = 1
    """
    params = []

    if date_query:
        sql += " AND entry_date = ?"
        params.append(date_query)

    if keyword_query:
        sql += " AND (subject LIKE ? OR body LIKE ? OR to_name LIKE ? OR from_name LIKE ?)"
        wildcard = f"%{keyword_query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    sql += " ORDER BY entry_date DESC, id DESC"
    rows = get_db().execute(sql, params).fetchall()

    return jsonify([serialize_entry(row) for row in rows])


@app.route("/api/entries", methods=["POST"])
@require_api_key
def create_entry():
    return jsonify({"error": "write endpoints reserved for backend admin tooling"}), 501


@app.route("/api/entries/<int:entry_id>", methods=["PUT", "DELETE"])
@require_api_key
def update_or_delete_entry(entry_id):
    return jsonify({"error": "write endpoints reserved for backend admin tooling", "id": entry_id}), 501

from flask import render_template_string

@app.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if not data or "password" not in data:
        return jsonify({"error": "missing password"}), 400

    if data["password"] != app.config["WRITE_API_KEY"]:
        return jsonify({"error": "unauthorized"}), 401

    return """
<!DOCTYPE html>
<html>
<head>
  <title>admin</title>
</head>
<body>
  <h1>compose journal entry</h1>
  <form method="POST" action="/admin-create-entry">
    <label>Date:<br>
      <input type="date" name="entry_date" required>
    </label><br><br>

    <label>To:<br>
      <input type="text" name="to_name" required>
    </label><br><br>

    <label>From:<br>
      <input type="text" name="from_name" required>
    </label><br><br>

    <label>Subject:<br>
      <input type="text" name="subject" required>
    </label><br><br>

    <label>Body:<br>
      <textarea name="body" rows="10" cols="50" required></textarea>
    </label><br><br>

    <button type="submit">create entry</button>
  </form>
</body>
</html>
"""
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
