import logging
import sys

logger = logging.getLogger("notifications")


def notify_would_send_email(company_name, submission_id, assigned_to, flags=None):
    message = (
        f"[NOTIFICATION STUB] Would send an email to {assigned_to} about "
        f"'{company_name}' (submission {submission_id}) needing review."
    )
    if flags:
        message += f"\n  FLAGS: {flags}"
    logger.info(message)
    print(message, flush=True, file=sys.stderr)
