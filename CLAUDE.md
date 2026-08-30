# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

This is an internal web application for corporate bank staff to manage customer
account onboarding and account maintenance. Customers upload required documents
(KYC/identity and business/financial), Claude analyzes those documents for
discrepancies and deficiencies, and the assigned reviewer is alerted by email
when issues are found so they can review the case inside the app.

**This handles confidential customer PII and financial data. Confidentiality and
accuracy are the top priorities for every decision made in this codebase —
above convenience, speed of development, or feature completeness.**

Detailed rules are split by topic under [.claude/rules/](.claude/rules/) and
load automatically:

- [confidentiality-compliance.md](.claude/rules/confidentiality-compliance.md) — read this first
- [tech-stack.md](.claude/rules/tech-stack.md)
- [domain-concepts.md](.claude/rules/domain-concepts.md)
- [analysis-requirements.md](.claude/rules/analysis-requirements.md)
- [open-decisions.md](.claude/rules/open-decisions.md)

## Development

No code has been scaffolded yet. Once the app is initialized, fill in:
- How to install dependencies and run the dev server.
- How to run tests and linting.
- How to run database migrations.
