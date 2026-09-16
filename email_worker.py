#!/usr/bin/env python3
import os
import smtplib
import ssl
from email.message import EmailMessage

from db import (
    list_pending_email_notifications,
    mark_email_notification_error,
    mark_email_notification_sent,
)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"


def send_email(item):
    if not SMTP_HOST or not SMTP_FROM:
        raise RuntimeError(
            "SMTP não configurado. Define SMTP_HOST e SMTP_FROM no .env."
        )

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = item["recipient"]
    msg["Subject"] = item["subject"]
    msg.set_content(item["body"])

    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        if SMTP_USE_TLS:
            server.starttls(context=context)

        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)

        server.send_message(msg)


def main():
    pending = list_pending_email_notifications(100)

    sent = 0
    errors = 0

    for item in pending:
        try:
            send_email(item)
            mark_email_notification_sent(item["id"])
            sent += 1
        except Exception as exc:
            mark_email_notification_error(item["id"], exc)
            errors += 1

    print(f"Emails processados: {len(pending)} | enviados: {sent} | erros: {errors}")


if __name__ == "__main__":
    main()
