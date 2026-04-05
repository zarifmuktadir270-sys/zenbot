"""
Facebook Page Scraper — Automatically reads products from seller's Facebook page posts.
This is what makes the setup "zero data entry" for sellers.
"""

import re
import httpx
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.models import Seller, Product


GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def fetch_page_posts(page_id: str, access_token: str, limit: int = 50) -> list[dict]:
    """Fetch recent posts from a Facebook page."""
    url = f"{GRAPH_API_BASE}/{page_id}/posts"
    params = {
        "access_token": access_token,
        "fields": "id,message,full_picture,created_time,permalink_url",
        "limit": limit,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])


def extract_product_info(post_text: str) -> dict:
    """
    Extract product name, price, and description from a Facebook post.
    Handles common BD e-commerce post formats:
    - "Product Name - 1200 BDT"
    - "Product Name\nPrice: 1200/-"
    - "Product Name | Price: ১২০০ টাকা"
    """
    if not post_text:
        return {}

    lines = post_text.strip().split("\n")
    name = lines[0].strip()[:200]  # First line is usually product name

    # Clean up name — remove emojis and excessive symbols
    name = re.sub(r'[^\w\s\-\|,।\u0980-\u09FF]', '', name).strip()
    if not name:
        name = post_text[:100].strip()

    # Extract price — look for common patterns
    price = None
    price_text = None
    price_patterns = [
        r'(?:price|মূল্য|দাম|prce)\s*[:\-]?\s*[৳$]?\s*([\d,]+)',  # Price: 1200
        r'([\d,]+)\s*(?:tk|taka|টাকা|bdt|/-)',                      # 1200 BDT / 1200/-
        r'[৳$]\s*([\d,]+)',                                          # ৳1200
        r'(?:only|মাত্র)\s*[৳$]?\s*([\d,]+)',                        # Only 1200
    ]

    for pattern in price_patterns:
        match = re.search(pattern, post_text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace(",", "")
            try:
                price = float(price_str)
                price_text = match.group(0).strip()
                break
            except ValueError:
                continue

    # Description — everything after first line, up to 500 chars
    description = "\n".join(lines[1:]).strip()[:500] if len(lines) > 1 else ""

    return {
        "name": name,
        "price": price,
        "price_text": price_text,
        "description": description,
    }


async def scrape_and_save_products(db: Session, seller: Seller) -> int:
    """
    Scrape products from a seller's Facebook page and save to database.
    Returns number of products found.
    """
    posts = await fetch_page_posts(seller.fb_page_id, seller.fb_page_access_token)

    count = 0
    for post in posts:
        post_text = post.get("message", "")
        if not post_text or len(post_text) < 10:
            continue

        # Skip non-product posts (shared links, status updates, etc.)
        # Product posts typically mention price or have certain keywords
        is_product = any(keyword in post_text.lower() for keyword in [
            "price", "tk", "taka", "টাকা", "bdt", "/-", "৳",
            "order", "অর্ডার", "stock", "স্টক", "available",
            "size", "সাইজ", "color", "কালার", "delivery", "ডেলিভারি",
        ])

        if not is_product:
            continue

        info = extract_product_info(post_text)
        if not info.get("name"):
            continue

        # Check if product already exists (by Facebook post ID)
        existing = db.query(Product).filter(
            Product.seller_id == seller.id,
            Product.fb_post_id == post["id"],
        ).first()

        if existing:
            # Update existing product
            existing.name = info["name"]
            existing.price = info.get("price")
            existing.price_text = info.get("price_text")
            existing.description = info.get("description")
            existing.image_url = post.get("full_picture")
            existing.raw_post_text = post_text
            existing.updated_at = datetime.now(timezone.utc)
        else:
            # Create new product
            product = Product(
                seller_id=seller.id,
                fb_post_id=post["id"],
                name=info["name"],
                price=info.get("price"),
                price_text=info.get("price_text"),
                description=info.get("description"),
                image_url=post.get("full_picture"),
                raw_post_text=post_text,
                is_available=True,
            )
            db.add(product)

        count += 1

    db.commit()
    return count


async def refresh_all_sellers(db: Session):
    """Refresh products for all active sellers. Run this on a schedule."""
    sellers = db.query(Seller).filter(Seller.is_active == True).all()
    for seller in sellers:
        try:
            await scrape_and_save_products(db, seller)
        except Exception as e:
            print(f"Error scraping seller {seller.fb_page_name}: {e}")
