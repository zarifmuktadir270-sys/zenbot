"""
Facebook OAuth Authentication Flow
Allows page owners to connect their Facebook page with one click
"""

import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import httpx
from datetime import datetime, timezone, timedelta

from app.models.database import get_db
from app.models.models import Seller
from app.config import settings
from app.services.page_scraper import scrape_and_save_products

router = APIRouter(prefix="/api/auth", tags=["auth"])


# === FACEBOOK OAUTH CONFIG ===
FB_APP_ID = settings.fb_app_id
FB_APP_SECRET = settings.fb_app_secret
FB_REDIRECT_URI = f"{settings.app_url}/api/auth/facebook/callback"

# Scopes needed for Messenger bot
FB_SCOPES = [
    "pages_show_list",           # List user's pages
    "pages_read_engagement",      # Read messages
    "pages_manage_metadata",      # Subscribe to webhooks
    "pages_messaging",            # Send messages
    "pages_manage_posts",         # Read page posts for products
]


@router.get("/facebook/login")
async def facebook_login():
    """
    Step 1: Redirect user to Facebook OAuth.
    User clicks "Connect My Facebook Page" → hits this endpoint.
    """
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={FB_APP_ID}"
        f"&redirect_uri={urllib.parse.quote(FB_REDIRECT_URI)}"
        f"&scope={','.join(FB_SCOPES)}"
        f"&response_type=code"
    )

    return {
        "auth_url": auth_url,
        "message": "Redirect user to this URL to start Facebook login"
    }


@router.get("/facebook/callback")
async def facebook_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Step 2: Facebook redirects here after user authorizes.
    Exchange authorization code for access token, then get page info.
    """

    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Facebook OAuth error: {error_description or error}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    async with httpx.AsyncClient() as client:
        # 1. Exchange code for user access token
        token_response = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id": FB_APP_ID,
                "client_secret": FB_APP_SECRET,
                "redirect_uri": FB_REDIRECT_URI,
                "code": code,
            }
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get access token: {token_response.text}"
            )

        token_data = token_response.json()
        user_access_token = token_data.get("access_token")

        if not user_access_token:
            raise HTTPException(status_code=500, detail="No access token in response")

        # 2. Get long-lived user access token (optional but recommended)
        long_lived_response = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": FB_APP_ID,
                "client_secret": FB_APP_SECRET,
                "fb_exchange_token": user_access_token,
            }
        )

        if long_lived_response.status_code == 200:
            long_lived_data = long_lived_response.json()
            user_access_token = long_lived_data.get("access_token", user_access_token)

        # 3. Get list of pages user manages
        pages_response = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": user_access_token}
        )

        if pages_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get pages: {pages_response.text}"
            )

        pages_data = pages_response.json()
        pages = pages_data.get("data", [])

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No Facebook pages found for this account. Please create a page first."
            )

        # 4. Auto-select first page (or let user choose if multiple pages)
        # For now, we'll register the first page found
        page = pages[0]
        page_id = page["id"]
        page_name = page["name"]
        page_access_token = page["access_token"]

        # 5. Check if page already registered
        existing_seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
        if existing_seller:
            raise HTTPException(
                status_code=400,
                detail=f"Page '{page_name}' is already registered!"
            )

        # 6. Subscribe page to webhook
        webhook_response = await client.post(
            f"https://graph.facebook.com/v18.0/{page_id}/subscribed_apps",
            params={
                "access_token": page_access_token,
                "subscribed_fields": "messages,messaging_postbacks,messaging_optins,message_deliveries,message_reads"
            }
        )

        if webhook_response.status_code != 200:
            print(f"Warning: Failed to subscribe webhook: {webhook_response.text}")

        # 7. Create seller in database
        seller = Seller(
            fb_page_id=page_id,
            fb_page_name=page_name,
            fb_page_access_token=page_access_token,
            delivery_info="Dhaka: 60 BDT, Outside Dhaka: 120 BDT",
            payment_methods="bKash, Nagad, COD",
            delivery_time="Dhaka: 1-2 days, Outside Dhaka: 3-5 days",
            return_policy="7 days return policy",
            plan="trial",
            plan_expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.add(seller)
        db.commit()
        db.refresh(seller)

        # 8. Scrape products from page
        try:
            product_count = await scrape_and_save_products(db, seller)
        except Exception as e:
            product_count = 0
            print(f"Initial scrape failed: {e}")

        # 9. Redirect to success page with data
        success_url = (
            f"/static/success.html?"
            f"seller_id={seller.id}"
            f"&page_name={urllib.parse.quote(page_name)}"
            f"&page_id={page_id}"
            f"&products={product_count}"
            f"&trial_expires={urllib.parse.quote(seller.plan_expires_at.isoformat())}"
        )
        return RedirectResponse(url=success_url, status_code=302)


@router.get("/facebook/pages")
async def list_user_pages(access_token: str):
    """
    Optional: Get list of pages for user to choose from.
    Call this after getting user access token if you want user to select page.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": access_token}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=response.text)

        data = response.json()
        pages = data.get("data", [])

        return {
            "pages": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "category": p.get("category", ""),
                }
                for p in pages
            ]
        }
