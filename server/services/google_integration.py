import base64
import mimetypes
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]

DRIVE_ROOT_FOLDER_NAME = "RAKBank Onboarding Submissions"

_drive_root_folder_id = None


def get_credentials():
    token_path = Path(config.GOOGLE_TOKEN_PATH)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")

    if not creds or not creds.valid:
        client_config = {
            "installed": {
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _get_or_create_root_folder(drive_service):
    global _drive_root_folder_id
    if _drive_root_folder_id:
        return _drive_root_folder_id

    query = (
        f"name = '{DRIVE_ROOT_FOLDER_NAME}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        _drive_root_folder_id = files[0]["id"]
        return _drive_root_folder_id

    folder_metadata = {
        "name": DRIVE_ROOT_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    _drive_root_folder_id = folder["id"]
    return _drive_root_folder_id


def _get_or_create_folder_in_parent(drive_service, name, parent_id):
    safe_name = name.replace("'", "\\'")
    if parent_id:
        query = (
            f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and trashed = false and '{parent_id}' in parents"
        )
    else:
        query = (
            f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false and 'root' in parents"
        )
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = drive_service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _create_drive_folder(drive_service, name, parent_id):
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive_service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _upload_directory(drive_service, local_dir, parent_folder_id):
    for entry in sorted(local_dir.iterdir()):
        if entry.is_dir():
            subfolder_id = _create_drive_folder(drive_service, entry.name, parent_folder_id)
            _upload_directory(drive_service, entry, subfolder_id)
        else:
            mimetype = mimetypes.guess_type(entry.name)[0] or "application/octet-stream"
            media = MediaFileUpload(str(entry), mimetype=mimetype, resumable=False)
            metadata = {"name": entry.name, "parents": [parent_folder_id]}
            drive_service.files().create(body=metadata, media_body=media, fields="id").execute()


def upload_submission_to_drive(local_folder, company_name, submission_id):
    """Returns (drive_url_or_None, error_or_None)."""
    local_folder = Path(local_folder)
    try:
        creds = get_credentials()
        drive_service = build("drive", "v3", credentials=creds)
        root_id = _get_or_create_root_folder(drive_service)
        submission_folder_id = _create_drive_folder(drive_service, local_folder.name, root_id)
        _upload_directory(drive_service, local_folder, submission_folder_id)
        return f"https://drive.google.com/drive/folders/{submission_folder_id}", None
    except HttpError as exc:
        return None, f"Drive API error: {exc}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def upload_profile_change_to_drive(local_folder, company_name, month_year):
    """Mirrors the local 'Profile Change / {Company} / {Month Year} / {leaf}'
    hierarchy into Drive. Returns (drive_url_or_None, error_or_None)."""
    local_folder = Path(local_folder)
    try:
        creds = get_credentials()
        drive_service = build("drive", "v3", credentials=creds)
        profile_change_root_id = _get_or_create_folder_in_parent(drive_service, "Profile Change", None)
        company_folder_id = _get_or_create_folder_in_parent(drive_service, company_name, profile_change_root_id)
        month_folder_id = _get_or_create_folder_in_parent(drive_service, month_year, company_folder_id)
        submission_folder_id = _create_drive_folder(drive_service, local_folder.name, month_folder_id)
        _upload_directory(drive_service, local_folder, submission_folder_id)
        return f"https://drive.google.com/drive/folders/{submission_folder_id}", None
    except HttpError as exc:
        return None, f"Drive API error: {exc}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def send_summary_email(subject, html_body, attachment_path=None):
    """Returns (True, None) on success, or (False, error_string) on failure.
    html_body is sent as an HTML email. attachment_path, if given, is attached as-is."""
    try:
        creds = get_credentials()
        gmail_service = build("gmail", "v1", credentials=creds)

        message = MIMEMultipart()
        message["to"] = config.EMAIL_RECIPIENT
        message["subject"] = subject
        message.attach(MIMEText(html_body, "html"))

        if attachment_path is not None:
            attachment_path = Path(attachment_path)
            if attachment_path.exists():
                mimetype = mimetypes.guess_type(attachment_path.name)[0] or "application/octet-stream"
                maintype, subtype = mimetype.split("/", 1)
                part = MIMEApplication(attachment_path.read_bytes(), _subtype=subtype)
                part.add_header("Content-Disposition", "attachment", filename=attachment_path.name)
                message.attach(part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, None
    except HttpError as exc:
        return False, f"Gmail API error: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
