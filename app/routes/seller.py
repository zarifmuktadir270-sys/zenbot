"""
Seller Dashboard API — Routes for sellers to manage their shop, view orders, etc.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from app.models.database import get_db
from app.models.models import Seller, Product, Customer, Order, Conversation
from app.services.page_scraper import scrape_and_save_products

router = APIRouter(prefix="/api/seller", tags=["seller"])


# === REQUEST MODELS ===

class SellerCreate(BaseModel):
    fb_page_id: str
    fb_page_name: str
    fb_page_access_token: str
    delivery_info: str = "ঢাকা: ৬০ টাকা, ঢাকার বাইরে: ১২০ টাকা"
    payment_methods: str = "বিকাশ, নগদ, ক্যাশ অন ডেলিভারি"
    delivery_time: str = "ঢাকা: ১-২ দিন, ঢাকার বাইরে: ৩-৫ দিন"
    return_policy: str = "৭ দিনের রিটার্ন পলিসি"


class SellerUpdate(BaseModel):
    delivery_info: Optional[str] = None
    payment_methods: Optional[str] = None
    delivery_time: Optional[str] = None
    return_policy: Optional[str] = None


# === ROUTES ===

@router.post("/register")
async def register_seller(data: SellerCreate, db: Session = Depends(get_db)):
    """
    Register a new seller. This is the onboarding endpoint.
    After registration, we automatically scrape their Facebook page for products.
    """
    # Check if seller already exists
    existing = db.query(Seller).filter(Seller.fb_page_id == data.fb_page_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="This Facebook page is already registered")

    seller = Seller(
        fb_page_id=data.fb_page_id,
        fb_page_name=data.fb_page_name,
        fb_page_access_token=data.fb_page_access_token,
        delivery_info=data.delivery_info,
        payment_methods=data.payment_methods,
        delivery_time=data.delivery_time,
        return_policy=data.return_policy,
        plan="trial",
        plan_expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)

    # Auto-scrape products from their page
    try:
        product_count = await scrape_and_save_products(db, seller)
    except Exception as e:
        product_count = 0
        print(f"Initial scrape failed: {e}")

    return {
        "seller_id": seller.id,
        "message": f"Registered! Found {product_count} products from your page.",
        "trial_expires": seller.plan_expires_at.isoformat(),
    }


@router.put("/{seller_id}/settings")
async def update_settings(seller_id: str, data: SellerUpdate, db: Session = Depends(get_db)):
    """Update seller's shop info (delivery, payment, etc.)."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    if data.delivery_info is not None:
        seller.delivery_info = data.delivery_info
    if data.payment_methods is not None:
        seller.payment_methods = data.payment_methods
    if data.delivery_time is not None:
        seller.delivery_time = data.delivery_time
    if data.return_policy is not None:
        seller.return_policy = data.return_policy

    db.commit()
    return {"message": "Settings updated"}


@router.post("/{seller_id}/refresh-products")
async def refresh_products(seller_id: str, db: Session = Depends(get_db)):
    """Manually trigger a product refresh from Facebook page."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    count = await scrape_and_save_products(db, seller)
    return {"message": f"Refreshed! Found {count} products."}


@router.get("/{seller_id}/dashboard")
async def get_dashboard(seller_id: str, db: Session = Depends(get_db)):
    """Get seller dashboard overview — orders, customers, conversations."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

    total_customers = db.query(Customer).filter(Customer.seller_id == seller_id).count()
    total_orders = db.query(Order).filter(Order.seller_id == seller_id).count()
    pending_orders = db.query(Order).filter(
        Order.seller_id == seller_id, Order.status == "pending"
    ).count()
    today_conversations = db.query(Conversation).filter(
        Conversation.seller_id == seller_id,
        Conversation.created_at >= today,
        Conversation.sender == "customer",
    ).count()
    total_products = db.query(Product).filter(Product.seller_id == seller_id).count()

    return {
        "shop_name": seller.fb_page_name,
        "plan": seller.plan,
        "stats": {
            "total_customers": total_customers,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "today_messages": today_conversations,
            "total_products": total_products,
        },
    }


@router.get("/{seller_id}/orders")
async def get_orders(seller_id: str, status: str = None, db: Session = Depends(get_db)):
    """Get all orders for a seller, optionally filtered by status."""
    query = db.query(Order).filter(Order.seller_id == seller_id)
    if status:
        query = query.filter(Order.status == status)

    orders = query.order_by(Order.created_at.desc()).limit(50).all()
    return [
        {
            "id": o.id,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "customer_address": o.customer_address,
            "items": o.items,
            "total_amount": o.total_amount,
            "payment_method": o.payment_method,
            "status": o.status,
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


@router.put("/{seller_id}/orders/{order_id}/status")
async def update_order_status(seller_id: str, order_id: str, status: str, db: Session = Depends(get_db)):
    """Update order status (confirm, ship, deliver, cancel)."""
    order = db.query(Order).filter(Order.id == order_id, Order.seller_id == seller_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    order.status = status
    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Order updated to {status}"}


@router.get("/{seller_id}/products")
async def get_products(seller_id: str, db: Session = Depends(get_db)):
    """Get all products for a seller."""
    products = db.query(Product).filter(Product.seller_id == seller_id).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "price_text": p.price_text,
            "description": p.description,
            "image_url": p.image_url,
            "is_available": p.is_available,
        }
        for p in products
    ]


@router.get("/{seller_id}/conversations")
async def get_conversations(seller_id: str, customer_id: str = None, db: Session = Depends(get_db)):
    """View conversation history. Optionally filter by customer."""
    query = db.query(Conversation).filter(Conversation.seller_id == seller_id)
    if customer_id:
        query = query.filter(Conversation.customer_id == customer_id)

    messages = query.order_by(Conversation.created_at.desc()).limit(100).all()
    return [
        {
            "id": m.id,
            "sender": m.sender,
            "message": m.message,
            "intent": m.intent,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
