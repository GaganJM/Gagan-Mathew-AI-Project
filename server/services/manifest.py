import json


def parse_structured_files(form, files):
    """Returns {section: {doc_name: [FileStorage, ...]}}. Raises ValueError on bad input."""
    raw = form.get("manifest")
    if not raw:
        raise ValueError("missing manifest")
    try:
        entries = json.loads(raw)
    except ValueError as exc:
        raise ValueError("manifest is not valid JSON") from exc

    structured = {}
    for entry in entries:
        section = entry["section"]
        doc_name = entry["docName"]
        field_name = entry["fieldName"]
        uploaded = files.getlist(field_name)
        if not uploaded:
            continue
        structured.setdefault(section, {}).setdefault(doc_name, []).extend(uploaded)
    return structured


def find_missing_mandatory(form, structured):
    """Server-side defense-in-depth: frontend already gates on this, but don't trust it."""
    entries = json.loads(form.get("manifest", "[]"))
    missing = []
    for entry in entries:
        if entry.get("mandatory") and not structured.get(entry["section"], {}).get(entry["docName"]):
            missing.append(f"{entry['section']}/{entry['docName']}")
    return missing
