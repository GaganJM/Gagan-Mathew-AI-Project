import json
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402  (must load before services that read env vars)
from services.company_extraction import extract_company_name  # noqa: E402
from services.email_report import build_email_html, build_maintenance_email_html  # noqa: E402
from services.excel_log import append_profile_change_row, append_submission_row, update_contact_info  # noqa: E402
from services.form_completeness import (  # noqa: E402
    check_account_opening_form,
    check_fatca_crs_form,
    check_generic_form,
    summarize_account_form_result,
    summarize_fatca_crs_result,
)
from services.google_integration import (  # noqa: E402
    send_summary_email,
    upload_profile_change_to_drive,
    upload_submission_to_drive,
)
from services.manifest import find_missing_mandatory, parse_structured_files  # noqa: E402
from services.notifications import notify_would_send_email  # noqa: E402
from services.pending_email import pop_pending_email, save_pending_email  # noqa: E402
from services.signing_authority import analyze_signing_authority, summarize_authority_result  # noqa: E402
from services.storage import build_profile_change_folder, build_submission_folder, save_structured_files  # noqa: E402
from services.ubo_tree import build_ownership_tree, render_org_chart_pdf, summarize_ownership_result  # noqa: E402

MAINTENANCE_SECTION_ID = "maintenance-documents"
MAINTENANCE_CHANGE_LABELS = {
    "additional-signatory": "Addition of a Signatory",
    "deletion-signatory": "Deletion of Signatory",
    "signing-instructions": "Change in Signing Instructions",
    "company-name": "Change Company Name",
    "shareholders": "Change in Shareholders",
}

TRADE_LICENSE_DOC_NAME = "Trade License / Certificate of Incorporation"
ENTITY_SECTION_ID = "entity-documents"
BANK_FORMS_SECTION_ID = "bank-forms"
ACCOUNT_OPENING_FORM_DOC_NAME = "Account Opening Form"
FATCA_CRS_DOC_NAME = "Corporate FATCA and CRS"
SHAREHOLDER_REGISTER_DOC_NAME = "Shareholder Register"
MOA_AOA_DOC_NAME = "Memorandum & Articles of Association (MOA/AOA) and any amendments"
SHAREHOLDER_RESOLUTION_DOC_NAME = "Shareholder Resolution (required only if signing powers are not mentioned in the MOA/AOA or POA)"
POWER_OF_ATTORNEY_DOC_NAME = "Power of Attorney"
SHAREHOLDER_DOCUMENTS_DOC_NAME = "Shareholder Documents"
ORGANIZATIONAL_CHART_DOC_NAME = "Organizational Chart"
UBO_SECTION_ID = "ubo-documents"
PASSPORT_COPY_DOC_NAME = "Passport Copy"
EMIRATES_ID_DOC_NAME = "Emirates ID / National ID"
PROOF_OF_ADDRESS_DOC_NAME = "Proof of Residential Address"
SOLE_OWNER_THRESHOLD = 99.9

app = Flask(__name__, static_folder=str(config.PUBLIC_DIR), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024


@app.before_request
def require_demo_auth():
    if not (config.DEMO_USERNAME and config.DEMO_PASSWORD):
        return None  # auth gate disabled (normal local dev)

    auth = request.authorization
    valid = (
        auth is not None
        and secrets.compare_digest(auth.username or "", config.DEMO_USERNAME)
        and secrets.compare_digest(auth.password or "", config.DEMO_PASSWORD)
    )
    if not valid:
        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="RAKBank Onboarding Demo"'},
        )
    return None


@app.get("/")
def index():
    return send_from_directory(config.PUBLIC_DIR, "index.html")


@app.get("/internal/uploads/<path:subpath>")
def internal_uploads(subpath):
    return send_from_directory(config.UPLOAD_ROOT, subpath)


@app.post("/api/submit-application")
def submit_application():
    try:
        structured = parse_structured_files(request.form, request.files)
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

    missing = find_missing_mandatory(request.form, structured)
    if missing:
        return jsonify(success=False, error="Missing mandatory documents: " + ", ".join(missing)), 400

    submission_id = uuid.uuid4().hex
    submitted_at = datetime.now(timezone.utc)

    trade_license_files = structured.get(ENTITY_SECTION_ID, {}).get(TRADE_LICENSE_DOC_NAME, [])
    result = extract_company_name(trade_license_files)

    if result and result.confidence in ("high", "medium") and result.company_name.strip():
        company_name = result.company_name.strip()
        confidence = result.confidence
        confirmed = True
    else:
        company_name = f"Unnamed Company - {submission_id[:8]}"
        confidence = "manual-entry-required"
        confirmed = False

    dest = build_submission_folder(config.UPLOAD_ROOT, company_name, submitted_at, submission_id)
    save_structured_files(structured, dest)

    flag_summaries = []
    bank_forms = structured.get(BANK_FORMS_SECTION_ID, {})

    account_form_files = bank_forms.get(ACCOUNT_OPENING_FORM_DOC_NAME, [])
    account_result = check_account_opening_form(account_form_files)
    flag_summaries.append(summarize_account_form_result(account_result))

    fatca_form_files = bank_forms.get(FATCA_CRS_DOC_NAME, [])
    fatca_result = check_fatca_crs_form(fatca_form_files)
    flag_summaries.append(summarize_fatca_crs_result(fatca_result))

    entity_docs = structured.get(ENTITY_SECTION_ID, {})
    shareholder_register_files = entity_docs.get(SHAREHOLDER_REGISTER_DOC_NAME, [])
    moa_aoa_files = entity_docs.get(MOA_AOA_DOC_NAME, [])
    shareholder_resolution_files = entity_docs.get(SHAREHOLDER_RESOLUTION_DOC_NAME, [])
    poa_files = entity_docs.get(POWER_OF_ATTORNEY_DOC_NAME, [])
    shareholder_documents_files = entity_docs.get(SHAREHOLDER_DOCUMENTS_DOC_NAME, [])
    org_chart_files = entity_docs.get(ORGANIZATIONAL_CHART_DOC_NAME, [])

    ubo_docs = structured.get(UBO_SECTION_ID, {})
    identity_files = (
        ubo_docs.get(PASSPORT_COPY_DOC_NAME, [])
        + ubo_docs.get(EMIRATES_ID_DOC_NAME, [])
        + ubo_docs.get(PROOF_OF_ADDRESS_DOC_NAME, [])
    )

    ownership_docs = (
        shareholder_register_files
        + moa_aoa_files
        + shareholder_documents_files
        + org_chart_files
        + identity_files
        + trade_license_files
    )
    tree_result = build_ownership_tree(ownership_docs)
    flag_summaries.append(summarize_ownership_result(tree_result))

    sole_owner_name = None
    top_level_nodes = [
        n for n in tree_result.data.get("nodes", []) if n.get("parent_id") is None
    ] if tree_result.data else []
    if len(top_level_nodes) == 1:
        only = top_level_nodes[0]
        if only.get("direct_percent") is not None and only["direct_percent"] >= SOLE_OWNER_THRESHOLD:
            sole_owner_name = only.get("name")

    # Deliberately excludes shareholder_documents_files: those are ownership/formation
    # documents for the applicant's *shareholders* (used for UBO conflict detection),
    # not the applicant entity itself, and including them here caused the model to
    # surface signatories/directors of shareholder companies as if they had signing
    # authority over the applicant's own account.
    authority_docs = moa_aoa_files + shareholder_resolution_files + poa_files
    authority_result = analyze_signing_authority(
        authority_docs, sole_owner_name=sole_owner_name, applicant_company_name=company_name
    )
    flag_summaries.append(summarize_authority_result(authority_result))

    chart_path = dest / "org-chart.pdf"
    render_org_chart_pdf(tree_result, company_name, chart_path)
    chart_url = "/internal/uploads/" + str(chart_path.relative_to(config.UPLOAD_ROOT)).replace("\\", "/")
    flag_summaries.append(f"Ownership chart (PDF): {chart_url}")

    drive_link, drive_error = upload_submission_to_drive(dest, company_name, submission_id)
    if drive_error:
        flag_summaries.append(f"Google Drive upload failed: {drive_error}")

    flags = " | ".join(flag_summaries)

    reference_number = append_submission_row(
        company_name=company_name,
        submitted_at_iso=submitted_at.isoformat(),
        assigned_to=config.ASSIGNED_REVIEWER,
        submission_id=submission_id,
        confidence=confidence,
        folder_path=str(dest),
        drive_link=drive_link,
        flags=flags,
    )

    notify_would_send_email(company_name, submission_id, config.ASSIGNED_REVIEWER, flags=flags)

    # The reviewer email is composed now (while the analysis results are at
    # hand) but not sent yet — it's stashed until the contact-info step fills
    # in the Excel row, so the Excel attachment on the email that actually
    # goes out is never missing the contact email/phone the customer is about
    # to provide on the next page.
    email_subject = f"Review needed: {company_name} ({reference_number})"
    email_html = build_email_html(
        company_name=company_name,
        reference_number=reference_number,
        account_result=account_result,
        fatca_result=fatca_result,
        tree_result=tree_result,
        authority_result=authority_result,
        company_name_confirmed=confirmed,
        extraction_confidence=confidence,
    )
    save_pending_email(reference_number, email_subject, email_html)

    return jsonify(
        success=True,
        submissionId=submission_id,
        referenceNumber=reference_number,
        companyName=company_name,
        companyNameConfirmed=confirmed,
        flags=flags,
    ), 200


@app.post("/api/submit-maintenance-request")
def submit_maintenance_request():
    try:
        structured = parse_structured_files(request.form, request.files)
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

    missing = find_missing_mandatory(request.form, structured)
    if missing:
        return jsonify(success=False, error="Missing mandatory documents: " + ", ".join(missing)), 400

    company_name = (request.form.get("companyName") or "").strip()
    if not company_name:
        return jsonify(success=False, error="Company / account name is required."), 400

    identifier_type = (request.form.get("identifierType") or "").strip()
    identifier_value = (request.form.get("identifierValue") or "").strip()
    if identifier_type == "cif" and len(identifier_value) == 7 and identifier_value.isdigit():
        cif_number, account_number = identifier_value, ""
    elif identifier_type == "account" and len(identifier_value) == 13 and identifier_value.isdigit():
        cif_number, account_number = "", identifier_value
    else:
        return jsonify(success=False, error="A valid 7-digit CIF number or 13-digit account number is required."), 400

    try:
        change_type_values = json.loads(request.form.get("changeTypes", "[]"))
    except ValueError:
        change_type_values = []
    change_type_labels = [MAINTENANCE_CHANGE_LABELS.get(v, v) for v in change_type_values]

    try:
        manifest_entries = json.loads(request.form.get("manifest", "[]"))
    except ValueError:
        manifest_entries = []
    bank_form_doc_names = [e["docName"] for e in manifest_entries if e.get("bankForm")]

    submission_id = uuid.uuid4().hex
    submitted_at = datetime.now(timezone.utc)

    dest = build_profile_change_folder(config.UPLOAD_ROOT, company_name, submitted_at, submission_id)
    save_structured_files(structured, dest)

    docs = structured.get(MAINTENANCE_SECTION_ID, {})

    bank_form_results = []
    for doc_name in bank_form_doc_names:
        files = docs.get(doc_name, [])
        result = check_generic_form(files, doc_name)
        bank_form_results.append((doc_name, result))

    other_document_names = [name for name in docs.keys() if name not in bank_form_doc_names]

    month_year = submitted_at.strftime("%B %Y")
    drive_link, drive_error = upload_profile_change_to_drive(dest, company_name, month_year)

    reference_number = append_profile_change_row(
        company_name=company_name,
        submitted_at_iso=submitted_at.isoformat(),
        cif_number=cif_number,
        account_number=account_number,
        change_types=change_type_labels,
        folder_path=str(dest),
        drive_link=drive_link,
    )

    notify_would_send_email(company_name, submission_id, config.ASSIGNED_REVIEWER, flags="Profile change request")

    # Stashed, not sent — see the matching comment in submit_application().
    email_subject = f"Profile Change - {company_name} - {reference_number}"
    email_html = build_maintenance_email_html(
        company_name=company_name,
        reference_number=reference_number,
        change_type_labels=change_type_labels,
        bank_form_results=bank_form_results,
        other_document_names=other_document_names,
    )
    save_pending_email(reference_number, email_subject, email_html)

    response_flags = []
    if drive_error:
        response_flags.append(f"Google Drive upload failed: {drive_error}")

    return jsonify(
        success=True,
        submissionId=submission_id,
        referenceNumber=reference_number,
        companyName=company_name,
        flags=" | ".join(response_flags),
    ), 200


@app.post("/api/submit-contact-info")
def submit_contact_info():
    data = request.get_json(silent=True) or {}
    reference_number = (data.get("referenceNumber") or "").strip()
    emails = [e.strip() for e in (data.get("emails") or []) if e and e.strip()]
    phones = [p.strip() for p in (data.get("phones") or []) if p and p.strip()]

    if not reference_number:
        return jsonify(success=False, error="Missing reference number."), 400
    if not emails:
        return jsonify(success=False, error="At least one contact email address is required."), 400
    if not phones:
        return jsonify(success=False, error="At least one contact number is required."), 400

    found = update_contact_info(reference_number, emails, phones)
    if not found:
        return jsonify(success=False, error="Could not find that submission in the tracker."), 404

    # Now that the Excel row has contact info, send the reviewer email that
    # was composed (but held back) at submission time — the attachment is
    # only ever generated fresh at send time, so it reflects this update.
    email_subject, email_html = pop_pending_email(reference_number)
    email_warning = None
    if email_subject and email_html:
        email_sent, email_error = send_summary_email(
            email_subject, email_html, attachment_path=config.EXCEL_LOG_PATH
        )
        if not email_sent:
            email_warning = f"Email send failed: {email_error}"

    return jsonify(success=True, emailWarning=email_warning), 200


@app.errorhandler(413)
def too_large(_e):
    return jsonify(success=False, error="Upload too large."), 413


@app.errorhandler(Exception)
def unhandled(exc):
    if isinstance(exc, HTTPException):
        return exc
    app.logger.exception("Unhandled error in submission")
    return jsonify(success=False, error="Internal error. Please try again."), 500


if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, port=config.PORT)
