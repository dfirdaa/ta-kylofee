"""WSGI/Vercel entry point. The implementation lives in app/ Blueprints."""

import importlib
import logging
import sys


# Vercel memuat file ini dengan nama modul ``app``. Karena package aplikasi juga
# bernama ``app``, ``from app import create_app`` akan menunjuk kembali ke file
# ini. Ganti entri sementara tersebut dengan package app/ sebelum import factory.
if __name__ == "app" and not hasattr(sys.modules.get("app"), "__path__"):
    sys.modules.pop("app", None)
    importlib.import_module("app")

try:
    from app import create_app

    app = create_app()
except Exception:
    # Vercel menangkap stderr; ini memastikan traceback import/cold-start tampil
    # lengkap di Function Logs, lalu exception tetap diteruskan ke runtime.
    logging.exception("KYLOFFEE gagal membuat WSGI app saat cold start.")
    raise
