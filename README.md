# RAKBank Wholesale Banking Portal (Prototype)

## Intent

This is an internal web application for corporate bank staff to manage
customer account onboarding and account maintenance. Customers upload
required documents (KYC/identity and business/financial), Claude analyzes
those documents for discrepancies and deficiencies, and the assigned
reviewer is alerted by email when issues are found so they can review the
case inside the app.

The goal is to cut down the manual effort of cross-checking corporate
account-opening paperwork — mandatory-field completeness on bank forms,
signing authority, and the full UBO (Ultimate Beneficial Owner) ownership
chain — by having Claude do a first pass and hand a reviewer a structured,
evidence-backed summary instead of a stack of raw PDFs.

**This handles confidential customer PII and financial data. Confidentiality
and accuracy are the top priorities for every decision made in this
codebase — above convenience, speed of development, or feature
completeness.** See [`.claude/rules/confidentiality-compliance.md`](.claude/rules/confidentiality-compliance.md)
before touching any code that handles customer documents or data.

This is a prototype/demo, not a production deployment — see
[Status & Open Decisions](#status--open-decisions) below.

## What it does

**Open an Account** — a new corporate customer uploads Bank Forms, Entity
Documents, and UBO Documents. On submission, Claude:
- Checks the Account Opening Form and FATCA/CRS form for missing
  asterisk-marked mandatory fields.
- Reconstructs the full ownership tree from shareholder/MOA documents,
  computes direct and indirect ownership percentages (aggregated across
  every branch a person holds a stake through), flags anyone at ≥25% as a
  UBO, and flags conflicting or incomplete shareholder documents.
- Determines who specifically has authority to open/operate/close the
  account, from the MOA/AOA, board/shareholder resolutions, and POAs.
- Renders a color-coded ownership org chart as a PDF.
- Saves all documents locally and to Google Drive, logs the submission to a
  persistent Excel tracker, and emails the reviewer a structured summary
  (never raw document content — see the compliance note above).

**Make Changes to Your Account** — an existing customer identifies their
account (company name + CIF or account number), selects one or more change
types (signatory addition/deletion, signing instructions, company name,
shareholders), and is shown a deduplicated list of the documents required
for exactly the changes they picked. Bank-form uploads get the same
mandatory-field completeness check.

Both flows end with a contact-info step and a reference number
(`WBG-26###` for account opening, `PC26###` for profile changes) recorded in
the Excel tracker.

## Tech stack

- **Backend**: Flask (Python), serving both the API and the static frontend.
- **Frontend**: vanilla HTML/CSS/JS — no framework, no build step.
- **AI analysis**: Anthropic API (Claude), called only from server-side
  service modules under `server/services/`, using structured JSON-schema
  outputs so every finding is a typed field with cited evidence rather than
  free text.
- **Document storage**: local `uploads/` (gitignored) + Google Drive.
- **Tracking**: a single persistent Excel workbook (`data/submissions.xlsx`,
  gitignored) via `openpyxl`.
- **Email**: Gmail API, link-only notification content.
- **PDF generation**: `xhtml2pdf` (pure Python, no external binary
  dependency) for the ownership org chart.

## Project structure

```
public/                      Static frontend (HTML/CSS/JS), served by Flask
server/
  app.py                     Flask routes / request orchestration
  config.py                  Env-driven configuration
  services/
    company_extraction.py    Company name extraction from trade license
    form_completeness.py     Mandatory-field completeness checks
    signing_authority.py     Signing authority analysis
    ubo_tree.py               Ownership tree + UBO computation + PDF org chart
    email_report.py          Reviewer email HTML composition
    google_integration.py    Google Drive upload + Gmail send
    excel_log.py             Persistent Excel tracker
    pending_email.py         Defers the reviewer email until contact info is captured
    file_blocks.py           Converts uploads to Claude API content blocks (incl. PDF page trimming)
    manifest.py, storage.py, notifications.py
.claude/rules/                Detailed project rules (confidentiality, tech stack, domain concepts, analysis requirements, open decisions)
```

## Getting started

1. **Clone and install dependencies**
   ```
   git clone https://github.com/GaganJM/rakbank-wholesale-banking-portal.git
   cd rakbank-wholesale-banking-portal
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment** — copy `.env.example` to `.env` and fill in:
   - `ANTHROPIC_API_KEY` — your Anthropic API key.
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — a Google Cloud OAuth
     client (type **Desktop app**) with the Drive and Gmail APIs enabled.
   - `EMAIL_RECIPIENT` — who receives reviewer notification emails.
   - Leave `DEMO_USERNAME`/`DEMO_PASSWORD` unset for normal local dev; set
     both (HTTP Basic Auth) before exposing the app publicly, e.g. via a
     tunnel — and set `FLASK_DEBUG=false` at the same time.

3. **Run it**
   ```
   python server/app.py
   ```
   Open `http://127.0.0.1:5000`. The first request that calls Google Drive
   or Gmail will open a browser window for one-time OAuth consent; the
   resulting token is cached at `server/google_token.json` (gitignored) and
   reused after that.

## Status & open decisions

This is a prototype built to demonstrate the workflow end-to-end, not a
finished production system. Before this handles real customer submissions,
the following need sign-off from the bank's compliance/legal/InfoSec teams
— see [`.claude/rules/open-decisions.md`](.claude/rules/open-decisions.md)
for the full list:

- Anthropic data-handling/enterprise agreement suitable for financial
  services data.
- Document retention and deletion policy.
- Full regulatory checklist per document type, beyond the starting
  discrepancy taxonomy in [`.claude/rules/domain-concepts.md`](.claude/rules/domain-concepts.md).
- MFA method and production authentication (this prototype has no user
  auth beyond the optional demo Basic Auth gate).
- On-prem/production infrastructure specifics (container platform, object
  storage, network egress rules).

Claude flags cases for human review — it never auto-approves or
auto-rejects an account; a reviewer always makes the final call.
