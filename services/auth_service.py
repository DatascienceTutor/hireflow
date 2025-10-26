"""
Authentication and user services:
- signup (create user + create confirmation code + send code)
- confirm email
- login (verify credentials)
- password reset request and confirm
"""

from sqlalchemy.orm import Session
from models.user import User
import bcrypt
import random
import string
import os
from typing import Tuple, Optional
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 0)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@example.com")


def _hash_password(plain: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    """
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _generate_code(length: int = 6, numeric: bool = True) -> str:
    """
    Generate a confirmation/reset code (default numeric).
    """
    if numeric:
        return "".join(random.choices(string.digits, k=length))
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _send_email(to_email: str, subject: str, body: str) -> None:
    """
    Send email using configured SMTP. If SMTP not configured, fallback to console output.
    """
    if SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = FROM_EMAIL
            msg["To"] = to_email
            msg.set_content(body)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        except Exception as e:
            # In production, log properly
            print(f"[auth_service] SMTP send failed: {e}")
            print("Falling back to console printing of the code.")
            print(body)
    else:
        # Demo fallback
        print("=== EMAIL (demo) ===")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        print("====================")


def signup_user(db: Session, email: str, role: str, password: str) -> Tuple[bool, str]:
    """
    Create a new user (not confirmed) and send confirmation code.
    Returns (success, message)
    """
    email = email.lower().strip()
    role = role.lower().strip()
    if role not in ("candidate", "manager"):
        return False, "Invalid role. Choose 'candidate' or 'manager'."

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return False, "Email already registered."

    hashed = _hash_password(password)
    code = _generate_code(6, numeric=True)
    user = User(
        email=email,
        password_hash=hashed,
        role=role,
        is_confirmed=0,
        confirmation_code=code,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    body = f"Your Hire Flow confirmation code is: {code}"
    email_sent = True
    try:
        _send_email(email, "Hire Flow -- Email confirmation", body)
    except Exception as e:
        print(f"[auth_service] Error sending email: {e}")
        email_sent = False

    if email_sent == True:
        return True, "Signup OK -- confirmation code sent to your email."
    else:
        return True, f"Signup OK -- email sending failed. Use this code: {code}"


def confirm_user(db: Session, email: str, code: str) -> Tuple[bool, str]:
    """
    Confirm a user's email with the code.
    """
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False, "User not found."
    if user.is_confirmed:
        return True, "User already confirmed."
    if user.confirmation_code and user.confirmation_code == code.strip():
        user.is_confirmed = 1
        user.confirmation_code = None
        db.commit()
        return True, "Email confirmed."
    return False, "Invalid confirmation code."


def authenticate_user(
    db: Session, email: str, password: str
) -> Tuple[bool, Optional[User], str]:
    """
    Authenticate user by email & password. Returns (ok, user, message)
    """
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False, None, "Invalid credentials."
    if not user.is_confirmed:
        return False, None, "Email not confirmed. Please confirm your email first."
    if _verify_password(password, user.password_hash):
        return True, user, "Login successful."
    return False, None, "Invalid credentials."


def request_password_reset(db: Session, email: str) -> Tuple[bool, str]:
    """
    Generate a reset code and send to user's email.
    """
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return (
            False,
            "If the email exists, a reset code has been sent.",
        )  # Avoid leaking existence
    code = _generate_code(6, numeric=True)
    user.reset_code = code
    db.add(user)
    db.commit()
    body = f"Your Hire Flow password reset code is: {code}"
    try:
        _send_email(email, "Hire Flow -- Password reset", body)
    except Exception as e:
        print(f"[auth_service] Error sending reset email: {e}")
    return True, "If the email exists, a reset code has been sent."


def confirm_password_reset(
    db: Session, email: str, code: str, new_password: str
) -> Tuple[bool, str]:
    """
    Confirm reset code and set new password.
    """
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False, "Invalid code or email."

    if user.reset_code and user.reset_code.strip() == code.strip():
        user.password_hash = _hash_password(new_password)
        user.reset_code = None
        db.add(user)
        db.commit()
        return True, "Password has been reset. Please login."
    return False, "Invalid reset code."
