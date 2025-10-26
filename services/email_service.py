from typing import Optional
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "0") or 0)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@example.com")

print(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)


def send_verification_email(to_email: str, code: str) -> Optional[str]:
    """
    Send a verification email containing the 6-digit code.
    Returns None on success via SMTP. If SMTP not configured or fails, returns the code (for dev fallback).
    """
    # Basic validation whether SMTP is configured
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD):
        # Not configured — return code for UI to display (development convenience)
        return code

    msg = EmailMessage()
    msg["Subject"] = "Your verification code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(f"Your verification code is: {code}\nThis code expires shortly.")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return None
    except Exception as exc:
        # On failure return code so developer can continue. Log to console.
        print(f"Failed sending email: {exc}")
        return code
