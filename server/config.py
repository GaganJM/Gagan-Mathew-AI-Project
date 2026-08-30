import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"

UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT", BASE_DIR / "uploads"))
EXCEL_LOG_PATH = Path(os.environ.get("EXCEL_LOG_PATH", BASE_DIR / "data" / "submissions.xlsx"))
ASSIGNED_REVIEWER = "Gagan"
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
PORT = int(os.environ.get("PORT", "5000"))

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_TOKEN_PATH = os.environ.get("GOOGLE_TOKEN_PATH", str(BASE_DIR / "server" / "google_token.json"))
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "gaganmathew00@gmail.com")

FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

# When set, every request must present these via HTTP Basic Auth. Leave both
# unset for normal local dev (no auth prompt); set both before exposing the
# app publicly (e.g. via a tunnel) so it isn't wide open to anyone with the URL.
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")
