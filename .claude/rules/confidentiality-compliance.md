# Confidentiality & Compliance

Read this before touching any code that handles customer documents or data.

- All uploaded documents and any data extracted from them are confidential
  customer PII/financial data. Treat them accordingly in every code path:
  encrypt at rest, TLS everywhere, no logging of document contents or PII to
  application logs, error trackers, or crash reports.
- Relevant regulatory frameworks to confirm with the bank's compliance/legal
  team before go-live: GLBA, FFIEC guidance, applicable state banking
  regulations, and SOC 2 if the org pursues it. Do not assume compliance —
  this codebase should make it easy for a human to verify compliance, not
  claim it.
- **Notification emails must never contain document contents, extracted PII,
  or discrepancy specifics.** Emails are link-only: a generic "a case needs
  your review" message plus a secure link back into the on-prem app, which
  requires login + MFA to view anything sensitive. This is what makes it safe
  to use a third-party transactional email service (SES/SendGrid) — the ESP
  only ever sees "case #1234 needs review," never customer data.
- Before sending any document content or extracted text to the Anthropic API,
  confirm the organization has data-handling terms in place suitable for
  financial services data. Treat this as a pre-launch checklist item to
  confirm with legal/InfoSec, not an assumption baked into the code.
- Enforce least-privilege access. Every document view, analysis run, and
  export must be written to an audit log (who, what customer/account, when,
  from where). The audit log itself is sensitive — protect it like customer
  data.
- Document retention/deletion period is not yet defined — it must come from
  the bank's regulatory requirements, not be invented in code. Until defined,
  do not build automatic deletion; only build retention as an explicit,
  configurable policy.
