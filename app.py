"""WSGI/Vercel entry point. The implementation lives in app/ Blueprints."""

from app import create_app


app = create_app()
