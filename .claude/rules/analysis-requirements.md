# Low-Error-Rate Analysis Requirements

The user has explicitly called out that the margin for error must be very
low. Design the analysis pipeline accordingly:

- Claude's output must be structured (typed fields), not free text:
  discrepancy type, severity, confidence, and cited evidence (which
  document/field the finding is based on). This lets a human reviewer verify
  a finding in seconds instead of re-reading source documents from scratch.
- Claude flags cases for human review — it never auto-approves or
  auto-rejects an account. A reviewer always makes the final call.
- Before go-live, build a small human-labeled eval set from past onboarding
  cases with known discrepancies, and test the prompt/pipeline against it.
  Re-run this eval whenever the prompt, model, or document pipeline changes.
- Log every analysis input and output (subject to the controls in
  [confidentiality-compliance.md](confidentiality-compliance.md)) — needed
  both for audit and for growing the eval set over time.
