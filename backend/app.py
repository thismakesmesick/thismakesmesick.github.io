import os
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, render_template_string, request
from flask_cors import CORS

app = Flask(__name__)


@app.route("/")
def home():
    return {"status": "Journal API running"}


app.config["DATABASE"] = os.getenv("JOURNAL_DB_PATH", "/tmp/journal.db")
app.config["WRITE_API_KEY"] = os.getenv("WRITE_API_KEY", "change-me")


ADMIN_COMPOSE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Compose</title>
  <style>
    body {
      margin: 0;
      padding: 24px;
      background: #f6f6f4;
      color: #1a1a1a;
      font-family: Georgia, "Times New Roman", serif;
    }

    .compose-wrap {
      max-width: 760px;
      margin: 0 auto;
    }

    .status {
      margin: 0 0 12px;
      padding: 10px 12px;
      border: 1px solid rgba(0, 0, 0, 0.25);
      background: #f3d6c4;
      font-size: 16px;
    }

    .email-card {
      border: 1px solid rgba(0, 0, 0, 0.25);
      padding: 16px;
      font-size: 18px;
      line-height: 1.4;
      background: #fff;
    }

    .email-row {
      margin: 0 0 10px;
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .email-row label {
      width: 88px;
      font-weight: bold;
      flex-shrink: 0;
    }

    input, textarea, button {
      font: inherit;
      color: inherit;
    }

    input[type="text"],
    input[type="date"],
    textarea {
      width: 100%;
      border: 1px solid rgba(0, 0, 0, 0.35);
      padding: 8px;
      background: #fff;
      box-sizing: border-box;
    }

    textarea {
      min-height: 220px;
      resize: vertical;
      line-height: 1.4;
    }

    .email-body {
      margin-top: 14px;
      padding-top: 10px;
      border-top: 1px solid rgba(0, 0, 0, 0.2);
    }

    .actions {
      margin-top: 16px;
    }

    button {
      border: 1px solid rgba(0, 0, 0, 0.35);
      background: #f6f6f4;
      padding: 8px 12px;
      cursor: pointer;
    }

    button:hover,
    button:focus-visible {
      background: #f3d6c4;
      outline: none;
    }
  </style>
</head>
<body>
  <main class="compose-wrap">
    {% if status_message %}
      <p class="status">{{ status_message }}</p>
    {% endif %}

    <form method="POST" action="/admin-create-entry" class="email-card">
      <div class="email-row">
        <label for="entry_date">Date</label>
        <input id="entry_date" type="date" name="entry_date" value="{{ values.entry_date }}" required>
      </div>

      <div class="email-row">
        <label for="to_name">To</label>
        <input id="to_name" type="text" name="to_name" value="{{ values.to_name }}" required>
      </div>

      <div class="email-row">
        <label for="from_name">From</label>
        <input id="from_name" type="text" name="from_name" value="{{ values.from_name }}" required>
      </div>

      <div class="email-row">
        <label for="subject">Subject</label>
        <input id="subject" type="text" name="subject" value="{{ values.subject }}" required>
      </div>

      <div class="email-body">
        <div class="email-row" style="align-items:flex-start;">
          <label for="body">Body</label>
          <textarea id="body" name="body" required>{{ values.body }}</textarea>
        </div>
      </div>

      <input type="hidden" name="password" value="{{ password }}">

      <div class="actions">
        <button type="submit">Create Entry</button>
      </div>
    </form>
  </main>
</body>
</html>
"""


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


def render_admin_compose_form(password, status_message=None, values=None):
    values = values or {}
    form_values = {
        "entry_date": values.get("entry_date", ""),
        "to_name": values.get("to_name", ""),
        "from_name": values.get("from_name", ""),
        "subject": values.get("subject", ""),
        "body": values.get("body", ""),
    }
    return render_template_string(
        ADMIN_COMPOSE_TEMPLATE,
        password=password,
        status_message=status_message,
        values=form_values,
    )


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


@app.route("/admin-login", methods=["POST"])
def admin_login():
    payload = request.get_json(silent=True) or {}
    password = payload.get("password", "")

    if not password:
        return jsonify({"error": "missing password"}), 400

    if password != app.config["WRITE_API_KEY"]:
        return jsonify({"error": "unauthorized"}), 401

    return render_admin_compose_form(password=password)


@app.route("/admin-create-entry", methods=["POST"])
def admin_create_entry():
    password = request.form.get("password", "")
    if password != app.config["WRITE_API_KEY"]:
        return jsonify({"error": "unauthorized"}), 401

    entry_date = request.form.get("entry_date", "").strip()
    to_name = request.form.get("to_name", "").strip()
    from_name = request.form.get("from_name", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    form_values = {
        "entry_date": entry_date,
        "to_name": to_name,
        "from_name": from_name,
        "subject": subject,
        "body": body,
    }

    if not all(form_values.values()):
        return render_admin_compose_form(
            password=password,
            status_message="Please fill in all fields before submitting.",
            values=form_values,
        ), 400

    db = get_db()
    db.execute(
        """
        INSERT INTO entries (entry_date, subject, to_name, from_name, body)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entry_date, subject, to_name, from_name, body),
    )
    db.commit()

    return render_admin_compose_form(
        password=password,
        status_message="Entry created successfully.",
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
