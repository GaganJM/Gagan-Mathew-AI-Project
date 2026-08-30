import re
from pathlib import Path


def sanitize_component(name, max_len=80):
    name = (name or "").strip()
    if not name:
        return "unnamed"
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.replace(" ", "-")
    name = re.sub(r"[^A-Za-z0-9\-_.]", "", name)
    name = name.strip("-.") or "unnamed"
    return name[:max_len]


def build_submission_folder(upload_root, company_name, submitted_at, submission_id):
    slug = sanitize_component(company_name)
    stamp = submitted_at.strftime("%Y%m%d-%H%M%S")
    folder = f"{slug}__{stamp}-{submission_id[:8]}"
    return Path(upload_root) / folder


def build_profile_change_folder(upload_root, company_name, submitted_at, submission_id):
    """Profile Change / {Company Name} / {Month Year} / {timestamp-id}"""
    slug = sanitize_component(company_name)
    month_year = submitted_at.strftime("%B %Y")
    stamp = submitted_at.strftime("%Y%m%d-%H%M%S")
    leaf = f"{stamp}-{submission_id[:8]}"
    return Path(upload_root) / "Profile Change" / slug / month_year / leaf


def save_structured_files(structured, dest_root):
    dest_root = Path(dest_root)
    for section, docs in structured.items():
        for doc_name, files in docs.items():
            doc_slug = sanitize_component(doc_name, max_len=100)
            section_dir = dest_root / sanitize_component(section, max_len=60)
            section_dir.mkdir(parents=True, exist_ok=True)
            for i, f in enumerate(files, start=1):
                ext = Path(f.filename or "").suffix.lower() or ""
                target = section_dir / f"{doc_slug}__{i}{ext}"
                f.stream.seek(0)
                f.save(target)
