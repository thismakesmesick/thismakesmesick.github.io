import os
import sqlite3
from flask import Flask, g, jsonify, render_template_string, request, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config["DATABASE"] = os.getenv("JOURNAL_DB_PATH", "/tmp/journal.db")
app.config["WRITE_API_KEY"] = os.getenv("WRITE_API_KEY", "change-me")


@app.route("/")
def home():
    return {"status": "Journal API running"}


# -------------------------
# DATABASE
# -------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db:
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
    db.commit()
    db.close()


def serialize_entry(row):
    return dict(row)


# -------------------------
# PUBLIC API ROUTES
# -------------------------

@app.route("/api/entries", methods=["GET"])
def list_entries():
    rows = get_db().execute(
        """
        SELECT id, entry_date, subject, to_name, from_name, body
        FROM entries
        ORDER BY entry_date DESC, id DESC
        """
    ).fetchall()
    return jsonify([serialize_entry(r) for r in rows])


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

    if not row:
        return jsonify({"error": "not found"}), 404

    return jsonify(serialize_entry(row))


# -------------------------
# ADMIN HTML TEMPLATE
# -------------------------

ADMIN_COMPOSE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Compose Journal Entry</title>
  <style>
    body {
      margin: 0;
      padding: 24px;
      background: #f6f6f4;
      font-family: Georgia, "Times New Roman", serif;
    }
    .compose-wrap {
      max-width: 760px;
      margin: 0 auto;
    }
    .email-card {
      border: 1px solid rgba(0,0,0,0.25);
      padding: 16px;
      background: #fff;
    }
    .email-row {
      margin-bottom: 12px;
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .email-row label {
      width: 80px;
      font-weight: bold;
    }
    input, textarea, button {
      font: inherit;
    }
    input[type="text"],
    input[type="date"],
    textarea {
      width: 100%;
      border: 1px solid rgba(0,0,0,0.35);
      padding: 8px;
      box-sizing: border-box;
    }
    textarea {
      min-height: 200px;
    }
    button {
      border: 1px solid rgba(0,0,0,0.35);
      background: #f6f6f4;
      padding: 8px 12px;
      cursor: pointer;
    }
    button:hover {
      background: #f3d6c4;
    }
  </style>
</head>
<body>
  <main class="compose-wrap">
    <form method="POST" action="/admin-create-entry" class="email-card">
      <div class="email-row">
        <label>Date</label>
        <input type="date" name="entry_date" required>
      </div>
      <div class="email-row">
        <label>To</label>
        <input type="text" name="to_name" required>
      </div>
      <div class="email-row">
        <label>From</label>
        <input type="text" name="from_name" required>
      </div>
      <div class="email-row">
        <label>Subject</label>
        <input type="text" name="subject" required>
      </div>
      <div class="email-row" style="align-items:flex-start;">
        <label>Body</label>
        <textarea name="body" required></textarea>
      </div>

      <input type="hidden" name="password" value="{{ password }}">

      <button type="submit">Create Entry</button>
    </form>
  </main>
</body>
</html>
"""


# -------------------------
# ADMIN ROUTES
# -------------------------

@app.route("/admin-login", methods=["POST"], strict_slashes=False)
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if password != app.config["WRITE_API_KEY"]:
        return jsonify({"error": "unauthorized"}), 401

    return render_template_string(ADMIN_COMPOSE_TEMPLATE, password=password)


@app.route("/admin-create-entry", methods=["POST"], strict_slashes=False)
def admin_create_entry():
    password = request.form.get("password", "")

    if password != app.config["WRITE_API_KEY"]:
        return jsonify({"error": "unauthorized"}), 401

    entry_date = request.form.get("entry_date")
    to_name = request.form.get("to_name")
    from_name = request.form.get("from_name")
    subject = request.form.get("subject")
    body = request.form.get("body")

    db = get_db()
    db.execute(
        """
        INSERT INTO entries (entry_date, subject, to_name, from_name, body)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entry_date, subject, to_name, from_name, body),
    )
    db.commit()

    # Redirect back to journal page
    return redirect("https://thismakesmesick.github.io/journal.html")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
