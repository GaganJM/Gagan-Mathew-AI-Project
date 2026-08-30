import json
from pathlib import Path

import config

PENDING_DIR = config.EXCEL_LOG_PATH.parent / "pending_emails"


def _path_for(reference_number):
    safe = "".join(c for c in reference_number if c.isalnum() or c in "-_")
    return PENDING_DIR / f"{safe}.json"


def save_pending_email(reference_number, subject, html):
    """Stashes an already-composed reviewer email so it can be sent later,
    once the contact-info step fills in the Excel row it will be attaching."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = _path_for(reference_number)
    path.write_text(json.dumps({"subject": subject, "html": html}), encoding="utf-8")


def pop_pending_email(reference_number):
    """Returns (subject, html) and deletes the stashed file, or (None, None)
    if nothing is pending for this reference number (e.g. already sent, or
    this reference number never had one)."""
    path = _path_for(reference_number)
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        path.unlink(missing_ok=True)
        return None, None
    path.unlink(missing_ok=True)
    return data.get("subject"), data.get("html")
