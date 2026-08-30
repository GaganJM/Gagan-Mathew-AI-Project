import html
import json
from datetime import datetime, timezone

from anthropic import Anthropic

from services.file_blocks import files_to_blocks

client = Anthropic()

MODEL = "claude-sonnet-5"

UBO_THRESHOLD = 25.0

TREE_SCHEMA = {
    "type": "object",
    "properties": {
        "applicant_name": {"type": "string", "description": "The applicant entity's name (the root of the tree)."},
        "nodes": {
            "type": "array",
            "description": (
                "A flat list of every shareholder/owner found across all provided documents, one entry per "
                "node. The applicant itself is NOT included as a node — nodes are the things that own a "
                "stake in the applicant or in another node."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "A short unique id for this node, e.g. 'n1', 'n2'."},
                    "name": {"type": "string", "description": "Name of the person or company."},
                    "type": {"type": "string", "enum": ["person", "company"]},
                    "parent_id": {
                        "type": ["string", "null"],
                        "description": (
                            "The id of the node this one holds shares IN. Use null if this node directly "
                            "owns a stake in the applicant entity itself (i.e. it is a direct shareholder of "
                            "the applicant)."
                        ),
                    },
                    "direct_percent": {
                        "type": ["number", "null"],
                        "description": "The percentage this node directly owns of its parent (or of the applicant, if parent_id is null). Null if not stated in the documents.",
                    },
                    "needs_more_documents": {
                        "type": "boolean",
                        "description": (
                            "True only for a 'company' type node whose OWN ownership breakdown is not "
                            "described anywhere in the provided documents, and whose stake could plausibly "
                            "reach 25% or more of the applicant once indirect ownership is computed."
                        ),
                    },
                    "documents_provided": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Which of the provided identity/KYC documents appear to belong to this specific "
                            "person or company by name match (e.g. 'Passport', 'Emirates ID', 'Trade License', "
                            "'Shareholder Register'). Empty array if none of the provided documents name this "
                            "person/company."
                        ),
                    },
                    "documents_missing": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Standard KYC documents that do NOT appear among the provided documents for this "
                            "node. For a 'person' node, check for: Passport, National/Emirates ID, Proof of "
                            "Residential Address. For a 'company' node, check for: Trade License (or "
                            "equivalent incorporation certificate), Shareholder Register / proof of its own "
                            "ownership."
                        ),
                    },
                },
                "required": [
                    "id",
                    "name",
                    "type",
                    "parent_id",
                    "direct_percent",
                    "needs_more_documents",
                    "documents_provided",
                    "documents_missing",
                ],
                "additionalProperties": False,
            },
        },
        "conflicting_documents": {
            "type": "array",
            "description": (
                "Any provided ownership/shareholder document that appears to describe a DIFFERENT "
                "entity's ownership structure than the applicant (e.g. a different company name, or a "
                "shareholder structure that contradicts the other documents rather than extending it) — "
                "do NOT merge these into the main 'nodes' tree. List them here instead so a human "
                "reviewer can compare both structures side by side."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "apparent_entity_name": {
                        "type": "string",
                        "description": "The company name this document actually appears to describe.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this document was excluded, e.g. 'names a different company than the applicant' or 'contradicts the shareholding percentages in the other shareholder register'.",
                    },
                    "nodes": {
                        "type": "array",
                        "description": "The ownership structure described in this excluded document, same flat-list shape as the main tree's nodes (id/name/type/parent_id/direct_percent only).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": ["person", "company"]},
                                "parent_id": {"type": ["string", "null"]},
                                "direct_percent": {"type": ["number", "null"]},
                            },
                            "required": ["id", "name", "type", "parent_id", "direct_percent"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["apparent_entity_name", "reason", "nodes"],
                "additionalProperties": False,
            },
        },
        "expired_or_expiring_documents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "document": {"type": "string", "description": "Which document, e.g. 'Trade License', 'Passport'."},
                    "holder": {"type": "string", "description": "Whose document this is (person/company name, or the applicant entity)."},
                    "expiry_date": {"type": "string", "description": "The expiry date as printed on the document."},
                    "status": {"type": "string", "enum": ["expired", "expiring_within_30_days"]},
                },
                "required": ["document", "holder", "expiry_date", "status"],
                "additionalProperties": False,
            },
            "description": "Any document among those provided whose printed expiry date is already past, or within 30 days, relative to today.",
        },
        "summary": {"type": "string", "description": "One or two sentence plain-English summary of the ownership structure found."},
    },
    "required": ["applicant_name", "nodes", "conflicting_documents", "expired_or_expiring_documents", "summary"],
    "additionalProperties": False,
}

TREE_PROMPT = (
    "These documents relate to a company applying to open a corporate bank account: "
    "a Shareholder Register, the entity's MOA/AOA, possibly additional "
    "shareholder/ownership documents or an organizational chart, and identity/KYC "
    "documents (passports, national/Emirates IDs, proof of address, trade licenses) "
    "for the entity and its shareholders/UBOs.\n\n"
    "1. Read the ownership-related documents together and reconstruct the full "
    "ownership tree: every shareholder of the applicant entity, and — if any "
    "shareholder is itself a company and its own ownership is described in these "
    "documents — that company's shareholders too, and so on down to natural persons "
    "wherever the documents allow. Do not guess or invent percentages that aren't "
    "stated. If a corporate shareholder's own ownership breakdown is simply not "
    "present anywhere in these documents, mark it with needs_more_documents=true "
    "instead of guessing.\n\n"
    "IMPORTANT — a corporate shareholder's ownership may be split across MULTIPLE "
    "separate documents (e.g. one shareholder document per individual owner of that "
    "company, rather than one document listing all of them together). Before "
    "concluding a corporate shareholder's ownership breakdown, check EVERY provided "
    "document for any mention of that specific company, not just the first document "
    "that names it — a company can easily have 2+ owners described across 2+ "
    "different files. Only mark needs_more_documents=true after confirming no other "
    "provided document adds another owner for that company. A common failure mode is "
    "stopping after finding one owner for a company when a second (or third) owner is "
    "named in a different document further down the file list — actively check for "
    "this rather than assuming the first document found is complete.\n\n"
    "2. If any ownership/shareholder document describes a DIFFERENT entity than the "
    "applicant, or a shareholding structure that contradicts rather than extends the "
    "other documents, do not merge it into the main tree — list it under "
    "conflicting_documents instead, with its own ownership structure so a reviewer "
    "can compare both side by side. Be conservative: only exclude a document this way "
    "if it genuinely doesn't fit (wrong company name, or numbers that don't "
    "reconcile), not just because it adds new information.\n\n"
    "3. For each node in the main tree, look through ALL the provided documents (not "
    "just the ownership documents) and note which ones name that specific person or "
    "company (documents_provided), and which standard KYC documents for that node "
    "type appear to be missing (documents_missing) — see the schema field "
    "descriptions for what 'standard' means per type.\n\n"
    "4. Separately, scan every document provided for a printed expiry date (trade "
    "licenses, passports, IDs, etc.) and list any that are already expired or expire "
    "within 30 days of {today} (today's date)."
)


def _today_str():
    return datetime.now(timezone.utc).date().isoformat()


class TreeResult:
    def __init__(self, data=None, error=None):
        self.data = data or {}
        self.error = error


def build_ownership_tree(files):
    """files: list of Werkzeug FileStorage objects (Shareholder Register, MOA/AOA, etc.)."""
    if not files:
        return TreeResult(error="no ownership documents provided")

    blocks = files_to_blocks(files)
    if not blocks:
        return TreeResult(error="no usable (PDF/image) ownership documents provided")
    blocks.append({"type": "text", "text": TREE_PROMPT.format(today=_today_str())})

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16384,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": blocks}],
            output_config={"format": {"type": "json_schema", "schema": TREE_SCHEMA}},
        )
    except Exception as exc:
        return TreeResult(error=type(exc).__name__)

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        return TreeResult(error="no text block in response")
    try:
        parsed = json.loads(text_block.text)
    except ValueError:
        return TreeResult(error="unparseable model output")

    _compute_indirect_percentages(parsed)
    return TreeResult(data=parsed)


def _compute_indirect_percentages(tree_data):
    nodes = tree_data.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}

    def indirect_percent(node):
        if "_indirect_percent" in node:
            return node["_indirect_percent"]
        direct = node.get("direct_percent")
        if direct is None:
            node["_indirect_percent"] = None
            return None
        parent_id = node.get("parent_id")
        if not parent_id or parent_id not in by_id:
            node["_indirect_percent"] = direct
            return direct
        parent_indirect = indirect_percent(by_id[parent_id])
        if parent_indirect is None:
            node["_indirect_percent"] = None
            return None
        result = direct * parent_indirect / 100.0
        node["_indirect_percent"] = result
        return result

    for n in nodes:
        n["indirect_percent_of_applicant"] = indirect_percent(n)

    # A single natural person can hold an indirect stake in the applicant via
    # more than one branch (e.g. they own a slice of two different
    # intermediate holding companies that each own part of the applicant).
    # UBO status is a function of their TOTAL stake across every branch, not
    # any one branch in isolation — a person under the 25% threshold on each
    # of two branches individually can still be a UBO once those are summed.
    # Matched by exact name (case/whitespace-insensitive) — the model doesn't
    # currently give us a stronger identity key like a passport number.
    totals_by_name = {}
    for n in nodes:
        if n.get("type") != "person":
            continue
        pct = n.get("indirect_percent_of_applicant")
        if pct is None:
            continue
        key = n["name"].strip().lower()
        totals_by_name[key] = totals_by_name.get(key, 0.0) + pct

    for n in nodes:
        if n.get("type") != "person":
            n["aggregate_indirect_percent"] = n.get("indirect_percent_of_applicant")
            n["is_ubo"] = False
            continue
        key = n["name"].strip().lower()
        total = totals_by_name.get(key)
        n["aggregate_indirect_percent"] = total
        n["is_ubo"] = bool(total is not None and total >= UBO_THRESHOLD)

    # Flag which person-nodes are one of >1 node sharing that name, so the
    # PDF/email can call out "combined across N holdings" instead of quietly
    # summing behind the scenes.
    name_counts = {}
    for n in nodes:
        if n.get("type") == "person":
            key = n["name"].strip().lower()
            name_counts[key] = name_counts.get(key, 0) + 1
    for n in nodes:
        if n.get("type") == "person":
            n["branch_count"] = name_counts.get(n["name"].strip().lower(), 1)


def summarize_ownership_result(result):
    if result.error:
        return "Ownership structure: could not verify (" + result.error + ")."
    data = result.data
    nodes = data.get("nodes", [])
    ubo_nodes = [n for n in nodes if n.get("is_ubo")]
    seen_ubo_names = set()
    unique_ubos = []
    for n in ubo_nodes:
        key = n["name"].strip().lower()
        if key not in seen_ubo_names:
            seen_ubo_names.add(key)
            unique_ubos.append(n)
    gaps = [n for n in nodes if n.get("needs_more_documents")]
    parts = [f"{len(unique_ubos)} UBO(s) identified at or above 25% (combining a person's stake across every branch they appear in)"]
    multi_branch_ubos = [n for n in unique_ubos if (n.get("branch_count") or 1) > 1]
    if multi_branch_ubos:
        names = ", ".join(
            f"{n['name']} ({n.get('aggregate_indirect_percent', 0):.1f}% combined across {n['branch_count']} holdings)"
            for n in multi_branch_ubos
        )
        parts.append("UBO status only reached by combining multiple holdings for: " + names)
    if gaps:
        names = ", ".join(n["name"] for n in gaps)
        parts.append(f"documents still needed for: {names}")

    missing_doc_notes = [
        f"{n['name']} missing {', '.join(n['documents_missing'])}"
        for n in nodes
        if n.get("documents_missing")
    ]
    if missing_doc_notes:
        parts.append("document gaps per person/entity: " + "; ".join(missing_doc_notes))

    conflicts = data.get("conflicting_documents") or []
    if conflicts:
        conflict_notes = "; ".join(
            f"a document appears to describe a different entity/structure ('{c.get('apparent_entity_name', '?')}') — {c.get('reason', '?')}"
            for c in conflicts
        )
        parts.append("CONFLICTING DOCUMENTS: " + conflict_notes)

    expiring = data.get("expired_or_expiring_documents") or []
    if expiring:
        exp_notes = "; ".join(
            f"{e.get('holder', '?')}'s {e.get('document', '?')} ({e.get('status', '?')}, expiry {e.get('expiry_date', '?')})"
            for e in expiring
        )
        parts.append("EXPIRED/EXPIRING DOCUMENTS: " + exp_notes)

    return "Ownership structure: " + "; ".join(parts) + "."


def _node_children(nodes, parent_id):
    return [n for n in nodes if n.get("parent_id") == parent_id]


INDENT_PX = 28

BRANCH_COLORS = [
    "#1e88e5",  # blue
    "#43a047",  # green
    "#8e24aa",  # purple
    "#fb8c00",  # orange
    "#00897b",  # teal
    "#d81b60",  # pink
    "#3949ab",  # indigo
    "#6d4c41",  # brown
]


def _render_node_pdf(node, nodes, depth, branch_color):
    pct = node.get("indirect_percent_of_applicant")
    pct_text = f"{pct:.1f}%" if isinstance(pct, (int, float)) else "unknown %"
    direct = node.get("direct_percent")
    direct_text = f"{direct:.1f}% direct" if isinstance(direct, (int, float)) else "direct % unknown"

    multi_branch = node.get("type") == "person" and (node.get("branch_count") or 1) > 1
    agg_pct = node.get("aggregate_indirect_percent")
    agg_text = ""
    if multi_branch and isinstance(agg_pct, (int, float)):
        agg_text = (
            f' <span style="color:#1a1a1a;font-weight:bold;">'
            f"(combined across {node['branch_count']} holdings: {agg_pct:.1f}% of applicant)</span>"
        )

    background = ""
    if node.get("is_ubo"):
        background = "background:#fdecea;"
    elif node.get("needs_more_documents"):
        background = "background:#fdf3e0;"

    badge = ""
    if node.get("is_ubo"):
        badge = ' <span style="color:#ff2e00;font-weight:bold;font-size:10px;">[UBO]</span>'
    elif node.get("needs_more_documents"):
        badge = ' <span style="color:#b8860b;font-weight:bold;font-size:10px;">[DOCS NEEDED]</span>'

    provided = node.get("documents_provided") or []
    missing = node.get("documents_missing") or []
    docs_html = ""
    if provided:
        docs_html += f'<div style="font-size:10px;color:#2e7d32;margin-top:3px;">Received: {html.escape(", ".join(provided))}</div>'
    if missing:
        docs_html += f'<div style="font-size:10px;color:#ff2e00;margin-top:2px;">Missing: {html.escape(", ".join(missing))}</div>'

    row = (
        f'<div style="margin-left:{depth * INDENT_PX}px;border-left:4px solid {branch_color};'
        f'{background}padding:6px 0 6px 10px;margin-top:6px;">'
        f'<span style="font-weight:bold;font-size:12px;">{html.escape(node["name"])}</span>{badge}'
        f'<div style="font-size:10px;color:#77808c;">{html.escape(node["type"].capitalize())} &middot; {direct_text} &middot; {pct_text} of applicant{agg_text}</div>'
        f"{docs_html}"
        f"</div>"
    )

    children = _node_children(nodes, node["id"])
    children_html = "".join(_render_node_pdf(c, nodes, depth + 1, branch_color) for c in children)
    return row + children_html


def _render_compact_node(node, nodes, depth=0):
    direct = node.get("direct_percent")
    direct_text = f"{direct:.1f}%" if isinstance(direct, (int, float)) else "?%"
    line = (
        f'<div style="font-size:10px;margin-left:{depth * 14}px;">'
        f'&bull; {html.escape(node["name"])} ({html.escape(node["type"])}) — {direct_text}</div>'
    )
    children = _node_children(nodes, node["id"])
    return line + "".join(_render_compact_node(c, nodes, depth + 1) for c in children)


def _conflict_comparison_html(main_nodes, applicant_name, conflicts):
    if not conflicts:
        return ""
    main_top = _node_children(main_nodes, None)
    main_col = (
        f'<div style="font-weight:bold;font-size:11px;">{html.escape(applicant_name)} (used in analysis)</div>'
        + "".join(_render_compact_node(n, main_nodes) for n in main_top)
    )

    right_sections = []
    for c in conflicts:
        c_nodes = c.get("nodes", [])
        c_top = _node_children(c_nodes, None)
        entity = c.get("apparent_entity_name", "?")
        reason = c.get("reason", "")
        right_sections.append(
            f'<div style="font-weight:bold;font-size:11px;color:#b8860b;">{html.escape(entity)} (excluded)</div>'
            f'<div style="font-size:9px;color:#7a1f00;margin-bottom:4px;">{html.escape(reason)}</div>'
            + "".join(_render_compact_node(n, c_nodes) for n in c_top)
        )
    right_col = '<hr style="border:none;border-top:1px dashed #ccc;margin:8px 0;">'.join(right_sections)

    return (
        '<div style="margin:14px 0 18px;">'
        '<div style="font-weight:bold;font-size:12px;color:#7a1f00;">'
        "&#9888; Conflicting document(s) detected — excluded from the ownership tree below. Compare structures:</div>"
        '<table style="width:100%;margin-top:8px;border-collapse:collapse;"><tr>'
        f'<td style="width:50%;vertical-align:top;border:1px solid #e2e5ea;padding:8px;">{main_col}</td>'
        f'<td style="width:50%;vertical-align:top;border:1px solid #f5a9a0;background:#fdecea;padding:8px;">{right_col}</td>'
        "</tr></table></div>"
    )


def _build_chart_body_html(tree_result, applicant_name):
    if tree_result.error:
        return f"<p>Could not build an ownership chart: {html.escape(tree_result.error)}</p>"

    data = tree_result.data
    nodes = data.get("nodes", [])
    top_level = _node_children(nodes, None)

    root_html = (
        '<div style="border:1px solid #141414;background:#141414;color:#fff;padding:8px 12px;">'
        f'<span style="font-weight:bold;font-size:13px;">{html.escape(applicant_name)}</span>'
        '<div style="font-size:10px;color:#c8c8c8;">Applicant entity</div>'
        "</div>"
    )
    branch_html_parts = []
    for i, n in enumerate(top_level):
        branch_color = BRANCH_COLORS[i % len(BRANCH_COLORS)]
        branch_label = (
            f'<div style="margin-top:18px;padding-top:6px;border-top:1px solid #eee;'
            f'font-size:10px;font-weight:bold;text-transform:uppercase;color:{branch_color};">'
            f"Branch {i + 1}</div>"
        )
        branch_html_parts.append(branch_label + _render_node_pdf(n, nodes, 1, branch_color))
    tree_html = root_html + "".join(branch_html_parts)

    summary = html.escape(data.get("summary", ""))
    conflicts = data.get("conflicting_documents") or []
    conflict_html = _conflict_comparison_html(nodes, applicant_name, conflicts)
    expiring = data.get("expired_or_expiring_documents") or []
    expiring_html = ""
    if expiring:
        items = "".join(
            f"<li><b>{html.escape(e.get('holder', '?'))}</b> — "
            f"{html.escape(e.get('document', '?'))}: {html.escape(e.get('status', '?').replace('_', ' '))} "
            f"(expiry {html.escape(e.get('expiry_date', '?'))})</li>"
            for e in expiring
        )
        expiring_html = (
            '<div style="background:#fdecea;border:1px solid #f5a9a0;padding:10px 14px;margin:10px 0 16px;font-size:11px;color:#7a1f00;">'
            f"<b>Expired/expiring documents:</b><ul>{items}</ul></div>"
        )

    return f'<p style="color:#55606f;font-size:12px;">{summary}</p>{conflict_html}{expiring_html}<div>{tree_html}</div>'


def render_org_chart_pdf(tree_result, applicant_name, out_path):
    from xhtml2pdf import pisa

    body = _build_chart_body_html(tree_result, applicant_name)
    page = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: Helvetica, Arial, sans-serif; }}
h1 {{ font-size: 18px; }}
</style>
</head><body>
<h1>Ownership Structure &amp; UBOs</h1>
{body}
</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pisa.CreatePDF(page, dest=f)
