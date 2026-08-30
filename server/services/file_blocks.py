import base64
import io
import mimetypes

from pypdf import PdfReader, PdfWriter

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _pdf_bytes(f, drop_pages=None, expected_page_count=None):
    """Returns the (possibly page-trimmed) raw PDF bytes for f.

    drop_pages/expected_page_count let a caller strip known-irrelevant pages
    (e.g. pure legal boilerplate with no fields) to cut input tokens on large
    forms. This only ever trims when the document's actual page count
    matches expected_page_count exactly — if a customer's upload has a
    different page count (different revision, missing/extra page, etc.) the
    full untouched document is sent instead, so a page-count mismatch can
    never cause real content to be silently dropped."""
    f.stream.seek(0)
    raw = f.stream.read()
    f.stream.seek(0)

    if not drop_pages:
        return raw

    try:
        reader = PdfReader(io.BytesIO(raw))
        if expected_page_count is not None and len(reader.pages) != expected_page_count:
            return raw
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in drop_pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        # Any parsing hiccup falls back to sending the original, untrimmed —
        # never worth risking a dropped page over a token-cost optimization.
        return raw


def file_to_block(f, drop_pages=None, expected_page_count=None):
    """Returns a document/image content block for the Claude API, or None if this
    file isn't a type the API accepts as visual/document input (e.g. a stray
    .txt/.docx upload)."""
    ext = (f.filename.rsplit(".", 1)[-1] if f.filename and "." in f.filename else "").lower()
    is_pdf = f.mimetype == "application/pdf" or ext == "pdf"
    is_image = (f.mimetype and f.mimetype.startswith("image/")) or ext in IMAGE_EXTENSIONS
    if not is_pdf and not is_image:
        return None

    if is_pdf:
        raw = _pdf_bytes(f, drop_pages=drop_pages, expected_page_count=expected_page_count)
        b64 = base64.standard_b64encode(raw).decode("utf-8")
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}

    f.stream.seek(0)
    b64 = base64.standard_b64encode(f.stream.read()).decode("utf-8")
    f.stream.seek(0)
    media_type = f.mimetype if f.mimetype and f.mimetype.startswith("image/") else (
        mimetypes.guess_type(f.filename or "")[0] or "image/jpeg"
    )
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}


def files_to_blocks(files, drop_pages=None, expected_page_count=None):
    """files: list of Werkzeug FileStorage. Returns a list of content blocks,
    skipping any files that aren't usable PDF/image types. drop_pages/
    expected_page_count are forwarded to file_to_block — see there."""
    return [
        b for b in (
            file_to_block(f, drop_pages=drop_pages, expected_page_count=expected_page_count)
            for f in files
        )
        if b is not None
    ]
