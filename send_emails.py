import argparse
import smtplib
import sys
import time
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from config import (
    EMAIL_SUBJECT,
    EMAIL_TEMPLATE_PATH,
    EVENT_NAME,
    GMAIL_APP_PASSWORD,
    QR_DIR,
    SENDER_EMAIL,
    SMTP_HOST,
    SMTP_PORT,
    init_db,
)

FALLBACK_HTML = """\
<!DOCTYPE html>
<html>
<body style="font-family:Arial,Helvetica,sans-serif;text-align:center;">
  <h2>{event}</h2>
  <p>Dear {name}, here is your personal QR code. Present it at the entrance gate. It works only once.</p>
  <img src="cid:qrcode" alt="Entry QR code" width="200" height="200">
</body>
</html>
"""

TEXT_TEMPLATE = """\
Dear {name},

Here is your personal QR code for {event}.
Present it at the entrance gate. It works only once.

Your unique QR code is attached to this email as an image.
Do not share this code. Once scanned, it cannot be used again.

See you at the gate!
"""


def load_html_template():
    if EMAIL_TEMPLATE_PATH.exists():
        return EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
    return FALLBACK_HTML


def render_html(name):
    return load_html_template().replace("{name}", name).replace("{event}", EVENT_NAME)


def build_message(attendee):
    msg = MIMEMultipart("mixed")
    subject = EMAIL_SUBJECT.replace("{event}", EVENT_NAME).replace("{name}", attendee["name"])
    msg["Subject"] = subject
    msg["From"] = formataddr((EVENT_NAME, SENDER_EMAIL))
    msg["To"] = attendee["email"]

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(TEXT_TEMPLATE.format(name=attendee["name"], event=EVENT_NAME), "plain"))
    alt.attach(MIMEText(render_html(attendee["name"]), "html"))

    qr_path = QR_DIR / f"{attendee['token']}.png"
    if not qr_path.exists():
        raise FileNotFoundError(f"QR image missing for {attendee['email']}: {qr_path}")
    image = MIMEImage(qr_path.read_bytes(), name=f"qrcode_{attendee['token']}.png")
    image.add_header("Content-ID", "<qrcode>")
    image.add_header("Content-Disposition", "inline", filename=f"qrcode_{attendee['token']}.png")

    alt.attach(image)
    msg.attach(alt)
    return msg


def connect_smtp():
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD is not set. Create one at https://myaccount.google.com/apppasswords "
            "(requires 2-Step Verification) and put it in the .env file."
        )
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
    return server


def send_batch(limit=100, dry_run=False, delay=2.0):
    conn = init_db()
    rows = conn.execute(
        "SELECT name, email, token FROM attendees WHERE sent=0 ORDER BY id LIMIT ?", (limit,)
    ).fetchall()
    if not rows:
        conn.close()
        return {"attempted": 0, "sent": 0, "failed": 0, "message": "No unsent attendees remaining."}

    if dry_run:
        conn.close()
        return {
            "attempted": len(rows),
            "sent": 0,
            "failed": 0,
            "message": f"DRY RUN: would send {len(rows)} emails from {SENDER_EMAIL}.",
            "recipients": [r["email"] for r in rows[:10]] + (["..."] if len(rows) > 10 else []),
        }

    server = connect_smtp()
    sent = failed = 0
    failures = []
    for i, attendee in enumerate(rows, 1):
        try:
            server.send_message(build_message(attendee))
        except smtplib.SMTPAuthenticationError:
            server.quit()
            raise RuntimeError("Gmail rejected the login. Check GMAIL_APP_PASSWORD / that 2-Step Verification is on.")
        except Exception:
            time.sleep(10)
            try:
                server.send_message(build_message(attendee))
            except Exception as exc:
                failed += 1
                failures.append(f"{attendee['email']}: {exc}")
                try:
                    server = connect_smtp()
                except Exception:
                    break
                continue
        sent += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE attendees SET sent=1, sent_at=? WHERE id=?", (now, attendee["id"]))
        conn.commit()
        print(f"[{i}/{len(rows)}] sent -> {attendee['email']}")
        if i < len(rows):
            time.sleep(delay)

    conn.close()
    try:
        server.quit()
    except Exception:
        pass
    return {"attempted": len(rows), "sent": sent, "failed": failed, "failures": failures}


def stats():
    conn = init_db()
    total = conn.execute("SELECT COUNT(*) AS c FROM attendees").fetchone()["c"]
    sent = conn.execute("SELECT COUNT(*) AS c FROM attendees WHERE sent=1").fetchone()["c"]
    scanned = conn.execute("SELECT COUNT(*) AS c FROM attendees WHERE scanned=1").fetchone()["c"]
    conn.close()
    return {"total": total, "emails_sent": sent, "emails_unsent": total - sent, "scanned": scanned, "not_scanned": total - scanned}


def main():
    parser = argparse.ArgumentParser(description="Send QR code emails via Gmail SMTP")
    parser.add_argument("--limit", type=int, default=100, help="Max emails this run (default 100)")
    parser.add_argument("--dry-run", action="store_true", help="Do not actually send")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between emails")
    args = parser.parse_args()
    try:
        result = send_batch(limit=args.limit, dry_run=args.dry_run, delay=args.delay)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Attempted: {result['attempted']} | Sent: {result['sent']} | Failed: {result['failed']}")
    for failure in result.get("failures", []):
        print(f"  FAILED: {failure}")
    if result.get("recipients") is not None:
        print("Recipients (first 10):", ", ".join(result["recipients"]))


if __name__ == "__main__":
    main()
