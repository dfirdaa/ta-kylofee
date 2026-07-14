from flask import current_app


def send_email(to_email, subject, html_content):
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        current_app.logger.info("Email registrasi tidak dikirim karena RESEND_API_KEY belum diisi.")
        return False
    try:
        import resend

        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": current_app.config["RESEND_FROM_EMAIL"],
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
        )
        return True
    except Exception:
        current_app.logger.exception("Pengiriman email registrasi gagal.")
        return False
