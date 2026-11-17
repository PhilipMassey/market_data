import os
import smtplib
from email.message import EmailMessage

DEFAULT_RECIPIENT_EMAIL = "philip.massey@gmail.com"
DEFAULT_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def send_email(
    subject: str,
    body: str,
    to_email: str = DEFAULT_RECIPIENT_EMAIL,
    sender_email: str | None = None,
    app_password: str | None = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 465,
) -> EmailMessage:
    """
    Sends a plain-text email via SMTP SSL (defaults to Gmail `smtp.gmail.com:465`).
    Reads `GMAIL_USER` / `GMAIL_APP_PASSWORD` (or `EMAIL_USER` / `EMAIL_PASSWORD`)
    from environment variables if not explicitly provided.
    """
    sender = sender_email or os.environ.get("GMAIL_USER") or os.environ.get("EMAIL_USER") or DEFAULT_RECIPIENT_EMAIL
    password = (
        app_password
        or os.environ.get("GMAIL_APP_PASSWORD")
        or os.environ.get("EMAIL_PASSWORD")
        or DEFAULT_APP_PASSWORD
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    if not password:
        raise ValueError(
            "Missing email password. Set the GMAIL_APP_PASSWORD (or EMAIL_PASSWORD) environment variable."
        )

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(sender, password)
        server.send_message(msg)

    print(f"Sent email '{subject}' to {to_email}.")
    return msg

