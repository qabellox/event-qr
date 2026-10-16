import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tokens.db"
QR_DIR = BASE_DIR / "qr_codes"
EXCEL_PATH = BASE_DIR / "attendees.xlsx"


def load_dotenv(path=BASE_DIR / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000").rstrip("/")
EVENT_NAME = os.environ.get("EVENT_NAME", "مؤتمر الصحة النفسية")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "adonandoqabello@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_SUBJECT = os.environ.get("EMAIL_SUBJECT", "تذكرتك الإلكترونية - {event}")
EMAIL_TEMPLATE_PATH = BASE_DIR / "email_template.html"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    QR_DIR.mkdir(exist_ok=True)
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            token TEXT NOT NULL UNIQUE,
            sent INTEGER NOT NULL DEFAULT 0,
            sent_at TEXT,
            scanned INTEGER NOT NULL DEFAULT 0,
            scanned_at TEXT
        )
        """
    )
    conn.commit()
    return conn
