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
from app.routes.admin import router as admin_router

# Create tables on first import (serverless cold start)
Base.metadata.create_all(bind=engine)

# Auto-migrate: add new columns to existing tables
from sqlalchemy import text, inspect
try:
    inspector = inspect(engine)
    seller_columns = [c['name'] for c in inspector.get_columns('sellers')]
    with engine.connect() as conn:
        for col_name, col_type in [
            ('admin_fb_user_id', 'VARCHAR'),
            ('bot_name', 'VARCHAR'),
            ('custom_instructions', 'TEXT'),
            ('learned_knowledge', 'TEXT'),
            ('bot_paused', 'BOOLEAN DEFAULT FALSE'),
            ('dashboard_pin', 'VARCHAR'),
        ]:
            if col_name not in seller_columns:
                conn.execute(text(f"ALTER TABLE sellers ADD COLUMN {col_name} {col_type}"))

        product_columns = [c['name'] for c in inspector.get_columns('products')]
        if 'stock' not in product_columns:
            conn.execute(text("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT -1"))

        conn.commit()
except Exception as e:
    print(f"Migration note: {e}")

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
app.include_router(admin_router)


@app.get("/")
async def root():
    """Serve landing page"""
    landing_file = os.path.join(os.path.dirname(__file__), "static", "landing.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
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


@app.get("/dashboard")
async def dashboard():
    dash_file = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dash_file):
        return FileResponse(dash_file)
    return {"error": "Dashboard not found"}


@app.get("/admin")
async def admin():
    admin_file = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file)
    return {"error": "Admin panel not found"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/debug")
async def debug():
    """Debug endpoint to check database state and webhook subscription."""
    from app.models.models import Seller
    import httpx

    db = SessionLocal()
    try:
        sellers = db.query(Seller).all()
        seller_data = []
        for s in sellers:
            info = {
                "id": s.id,
                "page_id": s.fb_page_id,
                "page_name": s.fb_page_name,
                "has_token": bool(s.fb_page_access_token),
                "has_admin_id": bool(getattr(s, 'admin_fb_user_id', None)),
                "is_active": s.is_active,
            }
            # Check webhook subscription
            if s.fb_page_access_token:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"https://graph.facebook.com/v21.0/{s.fb_page_id}/subscribed_apps",
                            params={"access_token": s.fb_page_access_token}
                        )
                        sub_data = resp.json()
                        if sub_data.get("data"):
                            info["subscribed_fields"] = sub_data["data"][0].get("subscribed_fields", [])
                        else:
                            info["subscribed_fields"] = sub_data
                except Exception as e:
                    info["subscription_error"] = str(e)
            seller_data.append(info)

        return {"sellers": seller_data, "total": len(sellers)}
    finally:
        db.close()


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
