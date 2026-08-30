import json

from anthropic import Anthropic

from services.file_blocks import files_to_blocks

client = Anthropic()

MODEL = "claude-sonnet-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "authority_clearly_established": {
            "type": "boolean",
            "description": "True if the documents clearly name at least one person who may open/close/operate bank accounts on the entity's behalf, OR the sole-owner case applies.",
        },
        "signatories": {
            "type": "array",
            "description": (
                "Every named individual identified across the provided documents as a signatory, "
                "director, officer, or otherwise authorized to act for the entity — not just the "
                "ones with account-opening power. Include everyone found, even if their authority is "
                "limited to day-to-day operation rather than opening/closing accounts."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "name_or_role": {"type": "string", "description": "The named individual, or the role if only a role is stated (e.g. 'the Managing Director')."},
                    "title": {"type": "string", "description": "Their title/position, e.g. 'Managing Director', 'Director', 'Authorized Signatory'. Empty string if not stated."},
                    "can_open_operate_close_account": {
                        "type": "boolean",
                        "description": "True only if this specific person is granted the power to OPEN, OPERATE, and CLOSE bank accounts on the entity's behalf — not just general signing authority on transactions.",
                    },
                    "basis": {"type": "string", "description": "The clause or basis for their role/authority (e.g. 'Article 12 of the AOA', 'Shareholder Resolution dated ...', 'Board Resolution')."},
                },
                "required": ["name_or_role", "title", "can_open_operate_close_account", "basis"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string", "description": "One or two sentence plain-English summary."},
    },
    "required": ["authority_clearly_established", "signatories", "summary"],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = (
    "These documents (the entity's MOA/AOA, and possibly a Board/Shareholder "
    "Resolution or Power of Attorney) relate to {applicant_desc} applying to open "
    "a corporate bank account.\n\n"
    "1. Identify every named individual across these documents who is a director, "
    "officer, or otherwise designated signatory FOR THAT APPLICANT ENTITY SPECIFICALLY "
    "— list all of them under 'signatories', with their title if stated.\n"
    "2. For EACH of those signatories, determine specifically whether they are "
    "granted the power to OPEN, OPERATE, and CLOSE bank accounts on the entity's "
    "behalf (can_open_operate_close_account) — this is often a named Managing "
    "Director, sole Director, or General Manager, sometimes granted via a separate "
    "resolution or power of attorney rather than the MOA/AOA itself. Do not mark "
    "someone true just because they are a signatory in general — only if the "
    "documents specifically grant them account opening/closing/operating rights.\n"
    "3. If no signatory can be found with this power anywhere in the documents, "
    "set authority_clearly_established=false and say so plainly in the summary "
    "rather than guessing.\n"
    "4. SCOPE: only report signatories/directors/officers of the applicant entity "
    "itself. If any of these documents mention a shareholder, parent, subsidiary, "
    "or other affiliated company's own directors, officers, or authorized "
    "signatories, do NOT include those people — they are not relevant to who can "
    "open/operate/close the applicant's own account.\n\n"
    "{sole_owner_note}"
)


class AuthorityResult:
    def __init__(self, data=None, error=None):
        self.data = data or {}
        self.error = error


def analyze_signing_authority(files, sole_owner_name=None, applicant_company_name=None):
    """files: list of Werkzeug FileStorage (MOA/AOA required, plus any Board/Shareholder
    Resolution or Power of Attorney provided) — for the applicant entity itself only,
    not any shareholder/parent/affiliated company's own documents.
    sole_owner_name: if the Shareholder Register showed a single 100% owner, pass their name here
    so the sole-owner special case doesn't require re-deriving it from the documents.
    applicant_company_name: the applicant entity's name, if known, so the prompt can name it
    explicitly rather than relying on the model to infer which entity is the applicant.
    """
    if not files:
        return AuthorityResult(error="no MOA/AOA or authorization documents provided")

    if sole_owner_name:
        sole_owner_note = (
            f"Note: the Shareholder Register shows '{sole_owner_name}' as the sole 100% "
            "owner of this entity. A sole owner may open, operate, and close accounts "
            "on their own even without a separate clause — if so, include them as a "
            "signatory with can_open_operate_close_account=true and basis 'Sole owner', "
            "and set authority_clearly_established=true."
        )
    else:
        sole_owner_note = ""

    applicant_desc = f"'{applicant_company_name}'" if applicant_company_name else "a company"

    blocks = files_to_blocks(files)
    if not blocks:
        return AuthorityResult(error="no usable (PDF/image) authorization documents provided")
    blocks.append({
        "type": "text",
        "text": PROMPT_TEMPLATE.format(applicant_desc=applicant_desc, sole_owner_note=sole_owner_note),
    })

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": blocks}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except Exception as exc:
        return AuthorityResult(error=type(exc).__name__)

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        return AuthorityResult(error="no text block in response")
    try:
        parsed = json.loads(text_block.text)
    except ValueError:
        return AuthorityResult(error="unparseable model output")

    return AuthorityResult(data=parsed)


def summarize_authority_result(result):
    if result.error:
        return "Signing authority: could not verify (" + result.error + ")."
    data = result.data
    signatories = data.get("signatories") or []
    openers = [p for p in signatories if p.get("can_open_operate_close_account")]

    if not data.get("authority_clearly_established") or not openers:
        opener_note = "NOT clearly established in the provided documents — needs manual review"
    else:
        opener_note = "; ".join(
            f"{p.get('name_or_role', '?')} ({p.get('title') or p.get('basis', '?')})" for p in openers
        )

    if signatories:
        all_names = "; ".join(
            f"{p.get('name_or_role', '?')}"
            + (f" ({p['title']})" if p.get("title") else "")
            + (" [CAN open/operate/close account]" if p.get("can_open_operate_close_account") else "")
            for p in signatories
        )
    else:
        all_names = "none identified"

    return (
        f"Signing authority — who can open/operate/close the account: {opener_note}. "
        f"All signatories identified: {all_names}."
    )
