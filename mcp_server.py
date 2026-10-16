from pathlib import Path

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("event-qr")


@mcp.tool()
def generate_qr_codes(excel_path: str = "") -> str:
    """Parse an attendees Excel file (columns containing 'name' and 'email'), create one
    unique token + QR code per person, and store them in the local database.
    Leave excel_path empty to use attendees.xlsx in the project folder.
    Safe to re-run: existing people keep their original token."""
    from generate import generate

    result = generate(excel_path or None)
    return f"Done. Total in database: {result['total']}, new added: {result['added']}. QR images in qr_codes/, workbook: attendees_with_qr.xlsx"


@mcp.tool()
def send_emails(limit: int = 100, dry_run: bool = True) -> str:
    """Send QR code emails via Gmail SMTP to attendees who have not received one yet.
    Always run with dry_run=true first to preview. Requires GMAIL_APP_PASSWORD in .env.
    limit controls how many emails this run (Gmail allows 500/day over SMTP)."""
    from send_emails import send_batch

    result = send_batch(limit=limit, dry_run=dry_run)
    if dry_run:
        return result["message"]
    line = f"Attempted: {result['attempted']}, sent: {result['sent']}, failed: {result['failed']}"
    if result.get("failures"):
        line += "\nFailures:\n" + "\n".join(result["failures"])
    return line


@mcp.tool()
def get_checkin_stats() -> str:
    """Return live statistics: total attendees, emails sent, people checked in."""
    from send_emails import stats

    s = stats()
    return (
        f"Total attendees: {s['total']}\n"
        f"Emails sent: {s['emails_sent']} (unsent: {s['emails_unsent']})\n"
        f"Checked in: {s['scanned']} (not yet: {s['not_scanned']})"
    )


@mcp.tool()
def get_unsent_list(limit: int = 20) -> str:
    """List attendees who still need their QR email."""
    from config import init_db

    conn = init_db()
    rows = conn.execute(
        "SELECT name, email FROM attendees WHERE sent=0 ORDER BY id LIMIT ?", (limit,)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS c FROM attendees WHERE sent=0").fetchone()["c"]
    conn.close()
    if not rows:
        return "Everyone already received their email."
    listing = "\n".join(f"- {r['name']} <{r['email']}>" for r in rows)
    return f"Unsent total: {total}. First {len(rows)}:\n{listing}"


@mcp.tool()
def export_status_excel(output_path: str = "") -> str:
    """Export current check-in status to an Excel file with Email Sent / Scanned columns.
    Leave output_path empty to save as checkin_status.xlsx in the project folder."""
    from generate import export_status

    path = export_status(output_path or None)
    return f"Exported to {path}"


if __name__ == "__main__":
    mcp.run()
