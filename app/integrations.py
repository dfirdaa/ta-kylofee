import uuid
from pathlib import Path

from flask import current_app, url_for
from werkzeug.utils import secure_filename


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


def save_menu_image(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return "", None
    extension = Path(uploaded_file.filename).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        return "", "Format gambar tidak valid. Gunakan PNG, JPG, JPEG, atau WEBP."

    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
    if cloud_name and api_key and api_secret:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
            public_id = f"{Path(secure_filename(uploaded_file.filename)).stem}-{uuid.uuid4().hex[:12]}"
            result = cloudinary.uploader.upload(
                uploaded_file.stream,
                public_id=public_id,
                folder=current_app.config.get("CLOUDINARY_FOLDER") or None,
                resource_type="image",
                overwrite=False,
            )
            return result.get("secure_url") or result.get("url"), None
        except Exception:
            current_app.logger.exception("Upload Cloudinary gagal.")
            return "", "Gagal mengunggah gambar ke Cloudinary. Periksa konfigurasi .env Anda."

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{secure_filename(uploaded_file.filename)}"
    uploaded_file.save(upload_folder / filename)
    return f"uploads/menu/{filename}", None


def menu_image_url(image_path):
    value = str(image_path or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "//")):
        return value
    return url_for("static", filename=value.lstrip("/"))

