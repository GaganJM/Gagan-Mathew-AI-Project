import json

from anthropic import Anthropic

from services.file_blocks import files_to_blocks

client = Anthropic()

MODEL = "claude-sonnet-5"


ACCOUNT_FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "appears_unfilled_template": {
            "type": "boolean",
            "description": "True if this looks like a blank/unfilled template rather than a completed application.",
        },
        "missing_mandatory_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Section name and, if the field repeats per person, which signatory/shareholder/authorized-person block it belongs to.",
                    },
                    "field": {"type": "string", "description": "The exact field label, as printed, that is marked with an asterisk."},
                },
                "required": ["location", "field"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string", "description": "One or two sentence plain-English summary."},
    },
    "required": ["appears_unfilled_template", "missing_mandatory_fields", "summary"],
    "additionalProperties": False,
}

ACCOUNT_FORM_PROMPT = (
    "This is RAKBank's Corporate Account Opening application form, possibly "
    "provided as multiple pages/files — read all of them together as one form. "
    "Every mandatory "
    "field on this form is marked with an asterisk (*) next to its label, and "
    "sections repeat this with a '* Mandatory Fields' legend. Some field blocks "
    "(e.g. signatory details, shareholder details) repeat multiple times for "
    "different people — check every repeated instance separately.\n\n"
    "Examine this submitted, filled-in form and identify every asterisk-marked "
    "field that appears to be left blank, unanswered, or unselected (for "
    "checkbox-style fields). For each one, give its section/location and the "
    "exact field label. If this document looks like an entirely blank template "
    "rather than a filled application, say so instead of listing every field.\n\n"
    "STRICT RULE: only include a field in missing_mandatory_fields if it is "
    "actually printed with a SINGLE asterisk (*) immediately next to its own "
    "label on the form. A field that merely seems important, commonly "
    "required, or contextually expected does NOT count — if you are not sure "
    "a specific field is asterisk-marked, leave it out rather than including "
    "it 'just in case'. Do not flag optional fields, and do not flag a field "
    "because a nearby or similar field elsewhere on the form happens to be "
    "asterisked.\n\n"
    "A double asterisk (**) is a DIFFERENT marker on this form — it points to "
    "a footnote (e.g. 'please indicate basis of authority, see table above') "
    "and does NOT mean the field is mandatory. Only a single '*' counts.\n\n"
    "A section header can itself carry an asterisk (e.g. 'DETAILS OF "
    "SHAREHOLDERS / OWNERSHIP*', 'KYC INFORMATION*') — this does not make "
    "every individual field inside that section mandatory. Only flag a field "
    "within such a section if that specific field's own label is separately "
    "asterisked.\n\n"
    "Never flag anything inside a 'FOR BANK USE ONLY' section (e.g. Lead "
    "Reference No., AECB Reference No., RO Code, RM Code, Domicile Branch, "
    "CIF, DSA Code) — those are completed by bank staff after submission, "
    "not by the customer, even though they are printed with asterisks.\n\n"
    "If a field's asterisk comes with a parenthetical condition (e.g. "
    "\"Mother's Maiden Name* (Mandatory only if applying for a Debit Card)\"), "
    "only flag it as missing if you can also confirm elsewhere in the form "
    "that condition is actually met (e.g. the debit card option was "
    "requested) — if you can't confirm the condition applies, leave it out.\n\n"
    "Fields that are commonly mistaken for mandatory on this specific form "
    "but are NOT asterisked, so must never be flagged: Issuing Authority, "
    "Industry Segment, Industry Sub Segment, Country of Incorporation, "
    "Building / Villa Name, Street / Location, Nearest Landmark, Employee "
    "No., Department, Occupation, Residence contact no., Mobile 2, Office "
    "Contact No., Email ID 2, Secondary Email ID, Website, Telephone, Fax."
)


FATCA_CRS_SCHEMA = {
    "type": "object",
    "properties": {
        "passive_nfe_selected": {
            "type": "boolean",
            "description": "Whether 'III. Passive NFE' (Section B, Entity Type, page 6) is ticked.",
        },
        "section_c_has_controlling_persons": {
            "type": ["boolean", "null"],
            "description": "If Passive NFE was selected: whether Section C (Controlling Person of Entity, page 7) lists at least one controlling person. Null if Passive NFE was not selected.",
        },
        "part7_completed": {
            "type": ["boolean", "null"],
            "description": "If Passive NFE was selected: whether Part 7 (Controlling Person - CRS Self Certification, page 12 onward) is actually filled in for the controlling person(s), not left blank. Null if Passive NFE was not selected.",
        },
        "other_incomplete_sections": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any other major section of the form left entirely blank.",
        },
        "summary": {"type": "string", "description": "One or two sentence plain-English summary."},
    },
    "required": [
        "passive_nfe_selected",
        "section_c_has_controlling_persons",
        "part7_completed",
        "other_incomplete_sections",
        "summary",
    ],
    "additionalProperties": False,
}

FATCA_CRS_PROMPT = (
    "This is RAKBank's Corporate FATCA/CRS Self-Certification form, possibly "
    "provided as multiple pages/files — read all of them together as one form. "
    "Examine this submitted, filled-in form and determine:\n\n"
    "1. On page 6, Section B ('Entity Type'), whether checkbox 'III. Passive NFE' "
    "(or its sub-options IIIa/IIIb) is ticked.\n"
    "2. If Passive NFE was selected: on page 7, Section C ('Controlling Person of "
    "Entity'), whether at least one controlling person is listed in the table.\n"
    "3. If Passive NFE was selected: starting on page 12, Part 7 ('Controlling "
    "Person - CRS Self Certification') — its own instructions say to fill this in "
    "for the account holder if it is a Passive NFE — whether this part has "
    "actually been filled in (personal details, address, tax residence) rather "
    "than left blank.\n"
    "4. Any other major section of the form left entirely blank.\n\n"
    "If Passive NFE was not selected, return null for the two Passive-NFE-"
    "dependent fields rather than guessing."
)


class CompletenessResult:
    def __init__(self, data=None, error=None):
        self.data = data or {}
        self.error = error


def _call_claude(files, prompt, schema, drop_pages=None, expected_page_count=None):
    if not files:
        return CompletenessResult(error="document not provided")
    blocks = files_to_blocks(files, drop_pages=drop_pages, expected_page_count=expected_page_count)
    if not blocks:
        return CompletenessResult(error="no usable (PDF/image) document provided")
    blocks.append({"type": "text", "text": prompt})
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": blocks}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except Exception as exc:
        return CompletenessResult(error=type(exc).__name__)

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        return CompletenessResult(error="no text block in response")
    try:
        parsed = json.loads(text_block.text)
    except ValueError:
        return CompletenessResult(error="unparseable model output")

    return CompletenessResult(data=parsed)


def generic_form_prompt(form_name):
    return (
        f"This is RAKBank's '{form_name}' form, possibly provided as multiple "
        "pages/files — read all of them together as one form. Mandatory fields "
        "on this form are typically marked with an asterisk (*) or otherwise "
        "indicated as required next to their label.\n\n"
        "Examine this submitted, filled-in form and identify every required "
        "field that appears to be left blank, unanswered, or unselected (for "
        "checkbox-style fields). For each one, give its section/location and "
        "the exact field label. If this document looks like an entirely blank "
        "template rather than a filled submission, say so instead of listing "
        "every field."
    )


def check_generic_form(files, form_name):
    return _call_claude(files, generic_form_prompt(form_name), ACCOUNT_FORM_SCHEMA)


def summarize_generic_form_result(form_name, result):
    if result.error:
        return f"{form_name}: could not verify ({result.error})."
    data = result.data
    if data.get("appears_unfilled_template"):
        return f"{form_name}: appears to be an unfilled template."
    missing = data.get("missing_mandatory_fields") or []
    if not missing:
        return f"{form_name}: no missing mandatory fields detected."
    items = "; ".join(f"{m.get('location', '?')} - {m.get('field', '?')}" for m in missing)
    return f"{form_name}: {len(missing)} mandatory field(s) appear incomplete: {items}."


# Verified directly against RAKBank's real Corporate Account Opening PDF
# (fixed template, same on every submission) — these field labels are
# printed WITHOUT an asterisk, so they must never be flagged as missing
# regardless of what the model concludes. The model has repeatedly flagged
# some of these despite explicit negative instructions in the prompt, so this
# is a deterministic backstop rather than relying on the prompt alone.
ACCOUNT_FORM_NON_MANDATORY_FIELDS = {
    "issuing authority",
    "industry segment",
    "industry sub segment",
    "country of incorporation",
    "corporate tax/ uae tin no",
    "corporate tax/uae tin no",
    "corporate tax id registration date",
    "vat registration number",
    "countries of operation",
    "countries of operation / trade place of business",
    "no. of employees",
    "number of branches",
    "building",
    "building / villa name",
    "building/villa name",
    "nearest landmark",
    "employee no.",
    "department",
    "occupation",
    "residence contact no.",
    "mobile 2",
    "office contact no.",
    "email id 2",
    "secondary email id",
    "website",
    "telephone",
    "fax",
    "please deliver all communication by",
}

# Anything located inside the bank-staff-only section is never the
# customer's responsibility to fill in, even though it's printed with
# asterisks on the real form (e.g. Lead Reference No., RM Code, CIF).
ACCOUNT_FORM_EXCLUDED_LOCATION_SUBSTRING = "bank use"


def _filter_account_form_false_positives(result):
    if result.error or not result.data:
        return result
    missing = result.data.get("missing_mandatory_fields") or []
    filtered = [
        m for m in missing
        if m.get("field", "").strip().lower() not in ACCOUNT_FORM_NON_MANDATORY_FIELDS
        and ACCOUNT_FORM_EXCLUDED_LOCATION_SUBSTRING not in m.get("location", "").strip().lower()
    ]
    result.data["missing_mandatory_fields"] = filtered
    return result


# Pages excluded from RAKBank's real Corporate Account Opening PDF before it's
# sent to Claude, to cut input-token cost on what is by far the largest
# document in the pipeline. The form is printed "1 of 19" .. "19 of 19" but
# there's an unnumbered cover page before that, so the file is 20 physical
# pages and (conveniently) 0-indexed page N == printed page "N of 19":
#   0  = unnumbered cover page — no content at all
#   4  = "4 of 19", Channels and Services — HAS real asterisked fields
#        (Authorized Signatory 1-10 "Full Name as per passport*"); dropping
#        this page means those are no longer checked. Deliberate tradeoff.
#   5  = "5 of 19", Sanction declaration — pure legal text, zero fields
#   6  = "6 of 19", Consent for disclosure of information / Account Signing
#        Instructions declaration — pure legal text, zero fields
#   15 = "15 of 19", Details of Shareholders/Ownership + Other Products —
#        no individually-asterisked fields (only the section header is
#        asterisked), so this page was already a no-op for this check
#   16 = "16 of 19", Customer Interest Declaration for Life Insurance — HAS
#        real asterisked fields (Name*/Mobile Phone*/Email ID*/Signature*,
#        twice); dropping this page means those are no longer checked.
#        Deliberate tradeoff.
#   19 = "19 of 19", "Get In Touch" contact footer — pure informational
#        text, zero fields
# Only applied when the uploaded PDF has exactly 20 physical pages — see
# _pdf_bytes in file_blocks.py for the fail-safe behavior on any other page
# count (sends the document untouched rather than risk cutting real content).
ACCOUNT_FORM_DROP_PAGES = {0, 4, 5, 6, 15, 16, 19}
ACCOUNT_FORM_EXPECTED_PAGE_COUNT = 20


def check_account_opening_form(files):
    result = _call_claude(
        files, ACCOUNT_FORM_PROMPT, ACCOUNT_FORM_SCHEMA,
        drop_pages=ACCOUNT_FORM_DROP_PAGES, expected_page_count=ACCOUNT_FORM_EXPECTED_PAGE_COUNT,
    )
    return _filter_account_form_false_positives(result)


def check_fatca_crs_form(files):
    return _call_claude(files, FATCA_CRS_PROMPT, FATCA_CRS_SCHEMA)


def summarize_account_form_result(result):
    if result.error:
        return "Account Opening Form: could not verify (" + result.error + ")."
    data = result.data
    if data.get("appears_unfilled_template"):
        return "Account Opening Form: appears to be an unfilled template."
    missing = data.get("missing_mandatory_fields") or []
    if not missing:
        return "Account Opening Form: no missing mandatory fields detected."
    items = "; ".join(f"{m.get('location', '?')} - {m.get('field', '?')}" for m in missing)
    return f"Account Opening Form: {len(missing)} mandatory field(s) appear incomplete: {items}."


def summarize_fatca_crs_result(result):
    if result.error:
        return "FATCA/CRS Form: could not verify (" + result.error + ")."
    data = result.data
    parts = []
    if data.get("passive_nfe_selected"):
        if data.get("section_c_has_controlling_persons") is False:
            parts.append("Passive NFE selected but Section C (Controlling Person of Entity, page 7) is empty")
        if data.get("part7_completed") is False:
            parts.append("Passive NFE selected but Part 7 (Controlling Person CRS Self Certification, page 12) is not completed")
    other = data.get("other_incomplete_sections") or []
    if other:
        parts.append("other incomplete sections: " + "; ".join(other))
    if not parts:
        return "FATCA/CRS Form: no issues detected."
    return "FATCA/CRS Form: " + "; ".join(parts) + "."
