# Recommended Tech Stack

No code exists yet, so nothing below is locked in — this is a recommendation
to build from, optimized for low defect rates and straightforward on-prem
deployment. Revise this file once a stack is actually chosen.

- **Frontend + API**: Next.js + TypeScript. Strong typing reduces the class of
  bugs that matter most in a low-error-tolerance app; API routes keep the
  server-side Claude/email calls out of the browser bundle.
- **Database**: PostgreSQL for structured data — customers, accounts,
  document metadata, review status, discrepancy records, audit log.
- **Document storage**: encrypted object storage, on-prem compatible (e.g.
  MinIO), not raw files in Postgres. Store only references/metadata in the DB.
- **AI analysis**: Anthropic API (Claude), called only from a thin server-side
  service layer. The API key must never reach the browser. All requests and
  responses are logged (see [analysis-requirements.md](analysis-requirements.md))
  for audit and eval purposes.
- **Auth**: email/password + TOTP-based MFA (e.g. via `otplib`), server-side
  sessions. No corporate SSO integration for now.
- **Email**: transactional ESP (SES/SendGrid), restricted by design to
  link-only notification content — see
  [confidentiality-compliance.md](confidentiality-compliance.md).
