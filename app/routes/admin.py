"""
Admin Panel API — For the app owner to manage all sellers, subscriptions, etc.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.models.database import get_db
from app.models.models import Seller, Product, Customer, Order, Conversation, Media

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_SECRET = "zenbot-admin-2024"


def check_key(key: str):
    if key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")


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


@router.get("/sellers/{seller_id}/conversations")
async def admin_conversations(seller_id: str, key: str = "", db: Session = Depends(get_db)):
    """View conversations for a specific seller."""
    check_key(key)
    customers = db.query(Customer).filter(Customer.seller_id == seller_id).all()
    result = []
    for c in customers:
        msgs = db.query(Conversation).filter(
            Conversation.seller_id == seller_id,
            Conversation.customer_id == c.id,
        ).order_by(Conversation.created_at.desc()).limit(5).all()
        if msgs:
            result.append({
                "customer_id": c.id,
                "customer_name": c.name or "Unknown",
                "total_messages": db.query(Conversation).filter(Conversation.customer_id == c.id).count(),
                "last_message": msgs[0].message[:100],
                "last_time": msgs[0].created_at.isoformat(),
            })
    result.sort(key=lambda x: x["last_time"], reverse=True)
    return result


@router.get("/sellers/{seller_id}/conversations/{customer_id}")
async def admin_conversation_detail(seller_id: str, customer_id: str, key: str = "", db: Session = Depends(get_db)):
    """View full conversation with a customer."""
    check_key(key)
    messages = db.query(Conversation).filter(
        Conversation.seller_id == seller_id,
        Conversation.customer_id == customer_id,
    ).order_by(Conversation.created_at.asc()).limit(200).all()
    return [{"sender": m.sender, "message": m.message, "time": m.created_at.isoformat()} for m in messages]


@router.get("/activity")
async def global_activity(key: str = "", db: Session = Depends(get_db)):
    """Get global activity across all sellers."""
    check_key(key)
    recent = db.query(Conversation).filter(
        Conversation.sender == "customer",
    ).order_by(Conversation.created_at.desc()).limit(30).all()

    result = []
    for m in recent:
        seller = db.query(Seller).filter(Seller.id == m.seller_id).first()
        customer = db.query(Customer).filter(Customer.id == m.customer_id).first()
        result.append({
            "shop": seller.fb_page_name if seller else "?",
            "customer": customer.name if customer else "?",
            "message": m.message[:80],
            "time": m.created_at.isoformat(),
        })
    return result


@router.post("/sellers/{seller_id}/toggle-bot")
async def admin_toggle_bot(seller_id: str, key: str = "", db: Session = Depends(get_db)):
    """Admin can pause/resume any seller's bot."""
    check_key(key)
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    seller.bot_paused = not getattr(seller, "bot_paused", False)
    db.commit()
    return {"message": f"Bot {'paused' if seller.bot_paused else 'resumed'} for {seller.fb_page_name}", "bot_paused": seller.bot_paused}
