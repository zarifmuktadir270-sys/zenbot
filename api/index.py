"""
Vercel Serverless Entry Point.
All requests route through here → FastAPI handles them.
"""

from app.main import app

# Vercel looks for a variable named `app` or `handler`
# FastAPI's ASGI app works directly with Vercel's Python runtime
