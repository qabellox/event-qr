import io
import os

from flask import Flask, jsonify, render_template, request, send_file

from config import EVENT_NAME, get_db, init_db
from generate import export_status

app = Flask(__name__)
init_db()


@app.get("/check/<token>")
def check(token):
    return render_template("checkin.html", token=token, event=EVENT_NAME)


@app.post("/api/validate")
def validate():
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    if not token or len(token) > 64:
        return jsonify({"status": "invalid"})
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE attendees SET scanned=1, scanned_at=datetime('now','localtime') "
            "WHERE token=? AND scanned=0",
            (token,),
        )
        conn.commit()
        if cursor.rowcount == 1:
            row = conn.execute("SELECT name FROM attendees WHERE token=?", (token,)).fetchone()
            return jsonify({"status": "first", "name": row["name"] if row else ""})
        row = conn.execute(
            "SELECT name, scanned_at FROM attendees WHERE token=?", (token,)
        ).fetchone()
        if row:
            return jsonify({"status": "used", "name": row["name"], "scanned_at": row["scanned_at"] or ""})
        return jsonify({"status": "invalid"})
    finally:
        conn.close()


@app.get("/scan")
def scan():
    return render_template("scan.html", event=EVENT_NAME)


@app.get("/admin")
def admin():
    return render_template("admin.html", event=EVENT_NAME)


@app.get("/api/attendees")
def api_attendees():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT name, email, sent, scanned, scanned_at FROM attendees ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    attendees = [dict(row) for row in rows]
    return jsonify(
        {
            "total": len(attendees),
            "sent": sum(r["sent"] for r in attendees),
            "scanned": sum(r["scanned"] for r in attendees),
            "attendees": attendees,
        }
    )


@app.get("/admin/export")
def admin_export():
    path = export_status()
    return send_file(path, as_attachment=True, download_name="checkin_status.xlsx")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
