"""
Admin Panel API — For the app owner to manage all sellers, subscriptions, etc.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.models.database import get_db
from app.models.models import Seller, Product, Customer, Order, Conversation

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_SECRET = "zenbot-admin-2024"


@router.get("/dashboard")
async def admin_dashboard(key: str = "", db: Session = Depends(get_db)):
    """Get overview stats for the admin."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    total_sellers = db.query(Seller).count()
    active_sellers = db.query(Seller).filter(Seller.is_active == True).count()
    total_customers = db.query(Customer).count()
    total_orders = db.query(Order).count()
    pending_orders = db.query(Order).filter(Order.status == "pending").count()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    today_messages = db.query(Conversation).filter(
        Conversation.created_at >= today
    ).count()

    return {
        "stats": {
            "total_sellers": total_sellers,
            "active_sellers": active_sellers,
            "total_customers": total_customers,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "today_messages": today_messages,
        }
    }


@router.get("/sellers")
async def list_sellers(key: str = "", db: Session = Depends(get_db)):
    """List all sellers with their details."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    sellers = db.query(Seller).order_by(Seller.created_at.desc()).all()
    result = []
    for s in sellers:
        order_count = db.query(Order).filter(Order.seller_id == s.id).count()
        customer_count = db.query(Customer).filter(Customer.seller_id == s.id).count()
        product_count = db.query(Product).filter(Product.seller_id == s.id).count()

        result.append({
            "id": s.id,
            "fb_page_id": s.fb_page_id,
            "fb_page_name": s.fb_page_name,
            "plan": s.plan,
            "plan_expires_at": s.plan_expires_at.isoformat() if s.plan_expires_at else None,
            "is_active": s.is_active,
            "bot_paused": getattr(s, "bot_paused", False),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "orders": order_count,
            "customers": customer_count,
            "products": product_count,
        })

    return result


@router.post("/sellers/{seller_id}/activate")
async def activate_seller(seller_id: str, key: str = "", db: Session = Depends(get_db)):
    """Activate a seller."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    seller.is_active = True
    db.commit()
    return {"message": f"{seller.fb_page_name} activated"}


@router.post("/sellers/{seller_id}/deactivate")
async def deactivate_seller(seller_id: str, key: str = "", db: Session = Depends(get_db)):
    """Deactivate a seller (block their bot)."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    seller.is_active = False
    db.commit()
    return {"message": f"{seller.fb_page_name} deactivated"}


@router.post("/sellers/{seller_id}/set-plan")
async def set_plan(seller_id: str, plan: str, days: int = 30, key: str = "", db: Session = Depends(get_db)):
    """Set a seller's subscription plan and duration."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    valid_plans = ["trial", "starter", "growth", "professional"]
    if plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan must be one of: {valid_plans}")

    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    seller.plan = plan
    seller.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    seller.is_active = True
    db.commit()

    return {
        "message": f"{seller.fb_page_name} set to {plan} plan for {days} days",
        "expires_at": seller.plan_expires_at.isoformat(),
    }


@router.delete("/sellers/{seller_id}")
async def delete_seller(seller_id: str, key: str = "", db: Session = Depends(get_db)):
    """Permanently delete a seller and all their data."""
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    # Delete related data
    db.query(Conversation).filter(Conversation.seller_id == seller_id).delete()
    db.query(Order).filter(Order.seller_id == seller_id).delete()
    db.query(Customer).filter(Customer.seller_id == seller_id).delete()
    db.query(Product).filter(Product.seller_id == seller_id).delete()
    db.delete(seller)
    db.commit()

    return {"message": f"{seller.fb_page_name} permanently deleted"}
