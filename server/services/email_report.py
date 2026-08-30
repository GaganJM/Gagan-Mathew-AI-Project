import html

SPACER = "<br><br><br>"


def _escape(s):
    return html.escape(str(s)) if s is not None else ""


def _account_form_detail(result):
    if result.error:
        return f"Could not verify ({_escape(result.error)})."
    data = result.data
    if data.get("appears_unfilled_template"):
        return "Appears to be an unfilled template."
    missing = data.get("missing_mandatory_fields") or []
    if not missing:
        return "No missing mandatory fields detected."
    items = "; ".join(f"{_escape(m.get('location', '?'))} - {_escape(m.get('field', '?'))}" for m in missing)
    return f"{len(missing)} mandatory field(s) appear incomplete: {items}."


def _fatca_detail(result):
    if result.error:
        return f"Could not verify ({_escape(result.error)})."
    data = result.data
    parts = []
    if data.get("passive_nfe_selected"):
        if data.get("section_c_has_controlling_persons") is False:
            parts.append("Passive NFE selected but Section C (Controlling Person of Entity, page 7) is empty.")
        if data.get("part7_completed") is False:
            parts.append("Passive NFE selected but Part 7 (Controlling Person CRS Self Certification, page 12) is not completed.")
    other = data.get("other_incomplete_sections") or []
    if other:
        parts.append("Other incomplete sections: " + "; ".join(_escape(o) for o in other) + ".")
    if not parts:
        return "No issues detected."
    return " ".join(parts)


def _account_openers(result):
    """Returns (openers, established) — the list of signatories flagged with
    account open/operate/close power, and whether that's clearly established."""
    if result.error:
        return [], False
    data = result.data
    signatories = data.get("signatories") or []
    openers = [p for p in signatories if p.get("can_open_operate_close_account")]
    return openers, bool(data.get("authority_clearly_established")) and bool(openers)


def _authority_headline(result):
    if result.error:
        return f"Could not verify ({_escape(result.error)})."
    openers, established = _account_openers(result)
    if not established:
        return (
            "<b>NOT clearly established</b> in the MOA/AOA, Board/Shareholder Resolution, "
            "Power of Attorney, or other shareholder documents provided — needs manual review."
        )
    names = "; ".join(
        _escape(p.get("name_or_role", "?")) + (f" ({_escape(p['title'])})" if p.get("title") else "")
        for p in openers
    )
    return f"<b>{names}</b>."


def _authority_detail(result):
    if result.error:
        return f"Could not verify ({_escape(result.error)})."
    data = result.data
    signatories = data.get("signatories") or []
    openers, established = _account_openers(result)

    if not established:
        opener_line = (
            "<b>Power to open/operate/close the account: NOT clearly established</b> "
            "in the provided documents — needs manual review."
        )
    else:
        names = "; ".join(
            _escape(p.get("name_or_role", "?")) + (f" ({_escape(p['title'])})" if p.get("title") else "")
            for p in openers
        )
        opener_line = f"<b>Power to open/operate/close the account:</b> {names}."

    if signatories:
        lines = "<br>".join(
            "&bull; "
            + _escape(p.get("name_or_role", "?"))
            + (f" — {_escape(p['title'])}" if p.get("title") else "")
            + (
                ' <span style="color:#2e7d32;font-weight:bold;">[can open/operate/close]</span>'
                if p.get("can_open_operate_close_account")
                else ""
            )
            for p in signatories
        )
        signatory_lines = f"All signatories identified:<br>{lines}"
    else:
        signatory_lines = "No named signatories identified in the provided documents."

    return f"{opener_line}<br><br>{signatory_lines}"


def _trade_license_detail(company_name, confirmed, confidence):
    if confirmed:
        return f"Company name extracted with {_escape(confidence)} confidence: {_escape(company_name)}."
    return "Could not confirm the company name automatically from this document — manual verification required."


def _shareholder_register_detail(tree_result):
    if tree_result.error:
        return f"Could not verify ownership structure ({_escape(tree_result.error)})."
    data = tree_result.data
    nodes = data.get("nodes", [])
    parts = []

    conflicts = data.get("conflicting_documents") or []
    for c in conflicts:
        reason = _escape(c.get("reason", "")).rstrip(".")
        parts.append(
            f"<b>One of the shareholder documents appears to describe a different entity/structure</b> "
            f"(\"{_escape(c.get('apparent_entity_name', '?'))}\") — {reason}. "
            "See the attached ownership chart PDF for both structures side by side."
        )

    gaps = [n for n in nodes if n.get("needs_more_documents")]
    if gaps:
        names = ", ".join(_escape(n["name"]) for n in gaps)
        parts.append(f"Additional ownership documents needed for: {names}.")

    if not parts:
        return "Ownership chain fully resolved from the documents provided."
    return " ".join(parts)


def _ubo_entries(tree_result):
    if tree_result.error:
        return []
    nodes = tree_result.data.get("nodes", [])
    expiring = tree_result.data.get("expired_or_expiring_documents") or []

    # A UBO can appear as more than one node (one per branch they hold a
    # stake through) — dedupe by name so they're reported once, with their
    # combined percentage and merged document notes across all their branches.
    by_name = {}
    order = []
    for n in nodes:
        if not n.get("is_ubo"):
            continue
        key = n["name"].strip().lower()
        if key not in by_name:
            by_name[key] = {"name": n["name"], "missing": set(), "branch_count": n.get("branch_count") or 1,
                             "aggregate_pct": n.get("aggregate_indirect_percent")}
            order.append(key)
        by_name[key]["missing"].update(n.get("documents_missing") or [])

    entries = []
    for key in order:
        info = by_name[key]
        parts = []
        if info["branch_count"] > 1 and isinstance(info["aggregate_pct"], (int, float)):
            parts.append(f"{info['aggregate_pct']:.1f}% combined across {info['branch_count']} holdings")
        if info["missing"]:
            parts.append("Missing: " + ", ".join(_escape(m) for m in sorted(info["missing"])))
        for e in expiring:
            if e.get("holder") == info["name"]:
                parts.append(
                    f"Expired: {_escape(e.get('document'))} (expiry {_escape(e.get('expiry_date'))})"
                )
        if not info["missing"]:
            parts.append("All required KYC documents received and appear valid.")
        entries.append((info["name"], "; ".join(parts)))
    return entries


def _doc_block(name, detail):
    return f'<p style="margin:0;"><b>{_escape(name)}</b><br>{detail}</p>'


def build_maintenance_email_html(
    company_name,
    reference_number,
    change_type_labels,
    bank_form_results,
    other_document_names,
):
    """bank_form_results: list of (form_name, CompletenessResult) for every
    bank-form document uploaded. other_document_names: list of the remaining
    (non-bank-form) document names that were uploaded, for a plain receipt
    list — these aren't field-checked, only confirmed present."""
    has_issue = False
    for _name, result in bank_form_results:
        if result.error:
            has_issue = True
            continue
        data = result.data
        if data.get("appears_unfilled_template") or (data.get("missing_mandatory_fields") or []):
            has_issue = True

    if bank_form_results and has_issue:
        headline = (
            '<p style="margin:0;background:#fdecea;border:1px solid #f5a9a0;padding:10px 14px;">'
            "<b>One or more bank forms have incomplete mandatory fields</b> — see the "
            "Bank Forms section below for details.</p>"
        )
    elif bank_form_results:
        headline = (
            '<p style="margin:0;background:#e8f5e9;border:1px solid #a5d6a7;padding:10px 14px;">'
            "<b>No incomplete mandatory fields detected</b> in the bank form(s) provided.</p>"
        )
    else:
        headline = (
            '<p style="margin:0;background:#eceff2;border:1px solid #cfd5dc;padding:10px 14px;">'
            "No bank forms with checkable mandatory fields were part of this request.</p>"
        )

    bank_form_blocks = [
        _doc_block(name, "Could not verify (" + _escape(result.error) + ").")
        if result.error
        else _doc_block(name, _account_form_style_detail(result))
        for name, result in bank_form_results
    ]

    other_doc_blocks = (
        [f'<p style="margin:0;">{_escape(n)} — received.</p>' for n in other_document_names]
        if other_document_names
        else ["<p>No other supporting documents were part of this request.</p>"]
    )

    sections = [
        ("Bank Forms — Completeness Check", bank_form_blocks or ["<p>No bank forms were part of this request.</p>"]),
        ("Other Documents Received", other_doc_blocks),
    ]

    section_html = ""
    for title, blocks in sections:
        section_html += f'<h2 style="font-size:15px;margin:24px 0 12px;">{_escape(title)}</h2>'
        section_html += SPACER.join(blocks)

    return f"""<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1a1a1a;">
<h1 style="font-size:18px;">{_escape(company_name)}</h1>
<p style="margin:0 0 6px;">Reference Number: <b>{_escape(reference_number)}</b></p>
<p style="margin:0 0 6px;">Change(s) requested: <b>{_escape("; ".join(change_type_labels))}</b></p>
<p>The submissions tracker (attached Excel, "Profile Change" sheet) has been updated with this request's details. The submitted documents have been saved both locally and to Google Drive under Profile Change / {_escape(company_name)} — see the attached tracker for the links.</p>
{headline}
{section_html}
</body></html>"""


def _account_form_style_detail(result):
    data = result.data
    if data.get("appears_unfilled_template"):
        return "Appears to be an unfilled template."
    missing = data.get("missing_mandatory_fields") or []
    if not missing:
        return "No missing mandatory fields detected."
    items = "; ".join(f"{_escape(m.get('location', '?'))} - {_escape(m.get('field', '?'))}" for m in missing)
    return f"{len(missing)} mandatory field(s) appear incomplete: {items}."


def build_email_html(
    company_name,
    reference_number,
    account_result,
    fatca_result,
    tree_result,
    authority_result,
    company_name_confirmed,
    extraction_confidence,
):
    bank_forms_blocks = [
        _doc_block("Account Opening Form", _account_form_detail(account_result)),
        _doc_block("Corporate FATCA and CRS", _fatca_detail(fatca_result)),
    ]

    company_doc_blocks = [
        f'<p style="margin:0;background:#fdecea;border:1px solid #f5a9a0;padding:10px 14px;">'
        f'<b>Who has the right to open, operate, and close the account:</b><br>'
        f'{_authority_headline(authority_result)}</p>',
        _doc_block("Memorandum & Articles of Association (MOA/AOA) and any amendments", _authority_detail(authority_result)),
        _doc_block(
            "Trade License / Certificate of Incorporation",
            _trade_license_detail(company_name, company_name_confirmed, extraction_confidence),
        ),
        _doc_block("Shareholder Register", _shareholder_register_detail(tree_result)),
        _doc_block(
            "Organizational Chart",
            "Ownership chart generated (PDF) — see the attached submissions log for the folder links.",
        ),
    ]

    ubo_entries = _ubo_entries(tree_result)
    if ubo_entries:
        ubo_blocks = [_doc_block(name, detail) for name, detail in ubo_entries]
    elif tree_result.error:
        ubo_blocks = [f"<p>Could not verify UBO documents ({_escape(tree_result.error)}).</p>"]
    else:
        ubo_blocks = ["<p>No UBOs (≥25% ownership) identified from the documents provided.</p>"]

    sections = [
        ("Bank Forms", bank_forms_blocks),
        ("Company Documents", company_doc_blocks),
        ("UBO Documents", ubo_blocks),
    ]

    section_html = ""
    for title, blocks in sections:
        section_html += f'<h2 style="font-size:15px;margin:24px 0 12px;">{_escape(title)}</h2>'
        section_html += SPACER.join(blocks)

    return f"""<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1a1a1a;">
<h1 style="font-size:18px;">{_escape(company_name)}</h1>
<p style="margin:0 0 6px;">Reference Number: <b>{_escape(reference_number)}</b></p>
<p>The submissions tracker (attached Excel) has been updated with this company's details. The submitted documents have been saved both locally and to Google Drive — see the attached tracker for the links to both.</p>
{section_html}
</body></html>"""
