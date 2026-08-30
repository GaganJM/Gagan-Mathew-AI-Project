import json

from anthropic import Anthropic

from services.file_blocks import files_to_blocks

client = Anthropic()  # reads ANTHROPIC_API_KEY from env

MODEL = "claude-haiku-4-5-20251001"

COMPANY_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {
            "type": "string",
            "description": (
                "The registered legal company/entity name exactly as printed on the "
                "document. Empty string if not found with confidence."
            ),
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["company_name", "confidence"],
    "additionalProperties": False,
}

PROMPT = (
    "This is a Trade License or Certificate of Incorporation submitted for a "
    "corporate bank account application (it may be provided as multiple pages "
    "or files — read all of them together). Extract the registered legal "
    "company/entity name exactly as printed. If the document shows both an "
    "Arabic and an English name, return the English legal name. If the "
    "document is illegible, cropped, or you cannot determine the company "
    "name with confidence, return an empty string for company_name and "
    "confidence \"low\" — do not guess."
)


class ExtractionResult:
    def __init__(self, company_name, confidence, error=None):
        self.company_name = company_name
        self.confidence = confidence
        self.error = error


def extract_company_name(files):
    """files: list of Werkzeug FileStorage objects (one or more pages/scans of the
    trade license / certificate of incorporation)."""
    if not files:
        return ExtractionResult(company_name="", confidence="low", error="no document provided")

    blocks = files_to_blocks(files)
    if not blocks:
        return ExtractionResult(company_name="", confidence="low", error="no usable (PDF/image) document provided")
    blocks.append({"type": "text", "text": PROMPT})

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1536,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": blocks}],
            output_config={"format": {"type": "json_schema", "schema": COMPANY_NAME_SCHEMA}},
        )
    except Exception as exc:  # network/auth/rate-limit/etc. — never crash the submission
        return ExtractionResult(company_name="", confidence="low", error=type(exc).__name__)

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        return ExtractionResult(company_name="", confidence="low", error="no text block in response")
    try:
        parsed = json.loads(text_block.text)
    except ValueError:
        return ExtractionResult(company_name="", confidence="low", error="unparseable model output")

    return ExtractionResult(
        company_name=parsed.get("company_name", ""),
        confidence=parsed.get("confidence", "low"),
    )
