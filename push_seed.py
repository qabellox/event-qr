import json
import sys
import urllib.request

from config import ADMIN_KEY, BASE_URL, init_db


def push():
    if not ADMIN_KEY:
        print("ERROR: ADMIN_KEY is not set in .env. Set it (and the same value on the server) first.")
        return 1
    if "localhost" in BASE_URL or "127.0.0.1" in BASE_URL:
        print(f"WARNING: BASE_URL is {BASE_URL}. Point it at your live server URL to sync.")
    conn = init_db()
    rows = conn.execute("SELECT name, email, token, sent, sent_at FROM attendees").fetchall()
    conn.close()
    if not rows:
        print("No attendees in the local database. Run generate.py first.")
        return 1
    payload = json.dumps({"attendees": [dict(r) for r in rows]}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + "/admin/import",
        data=payload,
        headers={"Content-Type": "application/json", "X-Admin-Key": ADMIN_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"ERROR: could not reach {BASE_URL} -> {exc}")
        return 1
    print(f"Synced {len(rows)} attendees to {BASE_URL}. added={result['added']} updated={result['updated']}")
    return 0


if __name__ == "__main__":
    sys.exit(push())
