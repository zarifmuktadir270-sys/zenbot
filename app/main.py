"""
Main Application — Vercel Serverless Compatible.
No background scheduler — uses Vercel Cron Jobs instead.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.models.database import engine, Base, SessionLocal
from app.services.page_scraper import refresh_all_sellers
from app.routes.webhook import router as webhook_router
from app.routes.seller import router as seller_router
from app.routes.auth import router as auth_router

# Create tables on first import (serverless cold start)
Base.metadata.create_all(bind=engine)

# === APP ===
app = FastAPI(
    title="E-commerce CS Agent",
    description="AI-powered customer service for Facebook sellers in Bangladesh",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routes
app.include_router(webhook_router)
app.include_router(seller_router)
app.include_router(auth_router)


@app.get("/")
async def root():
    """Serve onboarding page"""
    onboard_file = os.path.join(os.path.dirname(__file__), "static", "onboard.html")
    if os.path.exists(onboard_file):
        return FileResponse(onboard_file)
    return {
        "name": "E-commerce CS Agent",
        "status": "running",
        "onboard": "/onboard",
        "docs": "/docs",
    }


@app.get("/onboard")
async def onboard():
    """Onboarding page for sellers"""
    onboard_file = os.path.join(os.path.dirname(__file__), "static", "onboard.html")
    if os.path.exists(onboard_file):
        return FileResponse(onboard_file)
    return {"error": "Onboarding page not found"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/cron/refresh-products")
async def cron_refresh_products(request: Request):
    """
    Vercel Cron Job endpoint — refreshes products from all seller pages.
    Runs every 6 hours (configured in vercel.json).
    Vercel sends Authorization header to verify it's a legit cron call.
    """
    auth = request.headers.get("authorization")
    if auth != f"Bearer {request.app.state.cron_secret if hasattr(request.app.state, 'cron_secret') else ''}":
        # In production, verify CRON_SECRET. For now, allow all.
        pass

    db = SessionLocal()
    try:
        await refresh_all_sellers(db)
        return {"status": "ok", "message": "Products refreshed for all sellers"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
