"""
Seller Dashboard API — Routes for sellers to manage their shop, view orders, etc.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import hashlib
import base64

from app.models.database import get_db
from app.models.models import Seller, Product, Customer, Order, Conversation, Media, Coupon, has_feature, PLAN_FEATURES
from app.services.page_scraper import scrape_and_save_products
from app.config import settings as app_settings

router = APIRouter(prefix="/api/seller", tags=["seller"])


def verify_seller_pin(seller: Seller, pin: str) -> bool:
    """Verify seller's dashboard PIN."""
    stored = getattr(seller, "dashboard_pin", None)
    if not stored:
        return True  # No PIN set = open access (backward compat)
    return hashlib.sha256(pin.encode()).hexdigest() == stored


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
    bot_name: Optional[str] = None
    bot_personality: Optional[str] = None
    custom_instructions: Optional[str] = None
    welcome_message: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    price_text: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    stock: Optional[int] = None


class ProductCreate(BaseModel):
    name: str
    price: Optional[float] = None
    price_text: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    stock: Optional[int] = -1


class MediaCreate(BaseModel):
    name: str
    url: str
    media_type: str = "image"
    tags: str = ""


class LearnInput(BaseModel):
    knowledge: str


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
        plan_expires_at=datetime.now(timezone.utc) + timedelta(days=3),
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

    for field in ["delivery_info", "payment_methods", "delivery_time", "return_policy", "bot_name", "bot_personality", "custom_instructions", "welcome_message"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(seller, field, val)

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
            "stock": p.stock,
        }
        for p in products
    ]


@router.get("/{seller_id}/conversations")
async def get_conversations(seller_id: str, customer_id: str = None, db: Session = Depends(get_db)):
    """View conversation history."""
    query = db.query(Conversation).filter(Conversation.seller_id == seller_id)
    if customer_id:
        query = query.filter(Conversation.customer_id == customer_id)
    messages = query.order_by(Conversation.created_at.desc()).limit(100).all()
    return [
        {"id": m.id, "sender": m.sender, "message": m.message, "intent": m.intent, "created_at": m.created_at.isoformat()}
        for m in messages
    ]


@router.get("/{seller_id}/customers")
async def get_customers(seller_id: str, db: Session = Depends(get_db)):
    """Get all customers for a seller with their stats."""
    customers = db.query(Customer).filter(Customer.seller_id == seller_id).order_by(Customer.created_at.desc()).all()
    result = []
    for c in customers:
        msg_count = db.query(Conversation).filter(
            Conversation.seller_id == seller_id,
            Conversation.customer_id == c.id,
            Conversation.sender == "customer",
        ).count()
        last_msg = db.query(Conversation).filter(
            Conversation.seller_id == seller_id,
            Conversation.customer_id == c.id,
        ).order_by(Conversation.created_at.desc()).first()

        result.append({
            "id": c.id,
            "name": c.name or "Unknown",
            "phone": c.phone,
            "address": c.address,
            "total_orders": c.total_orders or 0,
            "total_messages": msg_count,
            "last_active": last_msg.created_at.isoformat() if last_msg else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@router.get("/{seller_id}/conversations/{customer_id}")
async def get_customer_conversation(seller_id: str, customer_id: str, db: Session = Depends(get_db)):
    """Get full conversation history with a specific customer."""
    messages = db.query(Conversation).filter(
        Conversation.seller_id == seller_id,
        Conversation.customer_id == customer_id,
    ).order_by(Conversation.created_at.asc()).limit(200).all()
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


@router.post("/{seller_id}/set-pin")
async def set_dashboard_pin(seller_id: str, pin: str = "", db: Session = Depends(get_db)):
    """Set or update the dashboard PIN for security."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    if pin:
        seller.dashboard_pin = hashlib.sha256(pin.encode()).hexdigest()
    else:
        seller.dashboard_pin = None
    db.commit()
    return {"message": "PIN updated" if pin else "PIN removed"}


@router.post("/{seller_id}/verify-pin")
async def verify_pin(seller_id: str, pin: str = "", db: Session = Depends(get_db)):
    """Verify seller dashboard PIN."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    if not getattr(seller, "dashboard_pin", None):
        return {"valid": True, "has_pin": False}

    valid = verify_seller_pin(seller, pin)
    return {"valid": valid, "has_pin": True}


@router.get("/{seller_id}/activity")
async def get_activity(seller_id: str, db: Session = Depends(get_db)):
    """Get recent activity feed for the seller."""
    # Recent conversations
    recent_msgs = db.query(Conversation).filter(
        Conversation.seller_id == seller_id,
        Conversation.sender == "customer",
    ).order_by(Conversation.created_at.desc()).limit(20).all()

    # Recent orders
    recent_orders = db.query(Order).filter(
        Order.seller_id == seller_id,
    ).order_by(Order.created_at.desc()).limit(10).all()

    activity = []
    for m in recent_msgs:
        customer = db.query(Customer).filter(Customer.id == m.customer_id).first()
        activity.append({
            "type": "message",
            "text": f"{customer.name or 'Customer'}: {m.message[:80]}",
            "intent": m.intent,
            "time": m.created_at.isoformat(),
        })
    for o in recent_orders:
        activity.append({
            "type": "order",
            "text": f"Order #{o.id[:8]} — {o.customer_name} ({o.status})",
            "time": o.created_at.isoformat(),
        })

    activity.sort(key=lambda x: x["time"], reverse=True)
    return activity[:30]


@router.get("/{seller_id}/settings")
async def get_settings(seller_id: str, db: Session = Depends(get_db)):
    """Get all seller settings for the dashboard."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    return {
        "bot_name": getattr(seller, "bot_name", "") or "AI Assistant",
        "bot_personality": getattr(seller, "bot_personality", "") or "friendly",
        "welcome_message": getattr(seller, "welcome_message", "") or "",
        "custom_instructions": getattr(seller, "custom_instructions", "") or "",
        "learned_knowledge": getattr(seller, "learned_knowledge", "") or "",
        "delivery_info": seller.delivery_info or "",
        "payment_methods": seller.payment_methods or "",
        "delivery_time": seller.delivery_time or "",
        "return_policy": seller.return_policy or "",
        "fb_page_name": seller.fb_page_name,
        "fb_page_id": seller.fb_page_id,
        "bot_paused": getattr(seller, "bot_paused", False),
        "has_pin": bool(getattr(seller, "dashboard_pin", None)),
        "plan": seller.plan,
        "plan_expires_at": seller.plan_expires_at.isoformat() if seller.plan_expires_at else None,
        "is_active": seller.is_active,
        "created_at": seller.created_at.isoformat() if seller.created_at else None,
    }


@router.post("/{seller_id}/toggle-bot")
async def toggle_bot(seller_id: str, db: Session = Depends(get_db)):
    """Pause or resume the AI bot."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    # Toggle the pause state
    current_state = getattr(seller, "bot_paused", False)
    seller.bot_paused = not current_state
    db.commit()

    status = "paused" if seller.bot_paused else "active"
    return {"message": f"Bot is now {status}", "bot_paused": seller.bot_paused}


# --- Product CRUD ---

@router.post("/{seller_id}/products")
async def add_product(seller_id: str, data: ProductCreate, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    product = Product(
        seller_id=seller_id, name=data.name, price=data.price,
        price_text=data.price_text, description=data.description,
        image_url=data.image_url, stock=data.stock,
    )
    db.add(product)
    db.commit()
    return {"id": product.id, "message": "Product added"}


@router.put("/{seller_id}/products/{product_id}")
async def edit_product(seller_id: str, product_id: str, data: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == seller_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field in ["name", "price", "price_text", "description", "image_url", "is_available", "stock"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(product, field, val)
    db.commit()
    return {"message": "Product updated"}


@router.delete("/{seller_id}/products/{product_id}")
async def delete_product(seller_id: str, product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == seller_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


# --- Learning ---

@router.post("/{seller_id}/learn")
async def add_knowledge(seller_id: str, data: LearnInput, db: Session = Depends(get_db)):
    """Owner teaches the bot something new. Persists forever."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    current = getattr(seller, "learned_knowledge", "") or ""
    seller.learned_knowledge = (current + "\n" + data.knowledge).strip()
    db.commit()
    return {"message": "Knowledge saved", "total_entries": len(seller.learned_knowledge.split("\n"))}


@router.delete("/{seller_id}/learn")
async def clear_knowledge(seller_id: str, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    seller.learned_knowledge = ""
    db.commit()
    return {"message": "Knowledge cleared"}


# --- Media ---

@router.get("/{seller_id}/media")
async def get_media(seller_id: str, db: Session = Depends(get_db)):
    media = db.query(Media).filter(Media.seller_id == seller_id).all()
    return [{"id": m.id, "name": m.name, "url": m.url, "media_type": m.media_type, "tags": m.tags} for m in media]


@router.post("/{seller_id}/media")
async def add_media(seller_id: str, data: MediaCreate, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    media = Media(seller_id=seller_id, name=data.name, url=data.url, media_type=data.media_type, tags=data.tags)
    db.add(media)
    db.commit()
    return {"id": media.id, "message": "Media added"}


@router.post("/{seller_id}/media/upload")
async def upload_media(
    seller_id: str,
    file: UploadFile = File(...),
    name: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upload a media file (image/video). Stored in DB as base64."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    # Read file (limit 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    content_type = file.content_type or "image/jpeg"
    media_type = "video" if "video" in content_type else "image"
    file_b64 = base64.b64encode(contents).decode()
    data_uri = f"data:{content_type};base64,{file_b64}"

    display_name = name or file.filename or "Uploaded file"

    base_url = app_settings.app_url.rstrip("/")
    media = Media(
        seller_id=seller_id,
        name=display_name,
        url="PLACEHOLDER",
        media_type=media_type,
        tags=tags,
        file_data=data_uri,
    )
    db.add(media)
    db.flush()
    media.url = f"{base_url}/api/seller/{seller_id}/media/serve/{media.id}"
    db.commit()

    return {"id": media.id, "name": display_name, "url": media.url, "message": "Uploaded"}


@router.get("/{seller_id}/media/serve/{media_id}")
async def serve_media(seller_id: str, media_id: str, db: Session = Depends(get_db)):
    """Serve an uploaded media file from DB."""
    media = db.query(Media).filter(Media.id == media_id, Media.seller_id == seller_id).first()
    if not media or not media.file_data:
        raise HTTPException(status_code=404, detail="Media not found")

    # Parse data URI: data:image/jpeg;base64,/9j/4AAQ...
    data_uri = media.file_data
    if data_uri.startswith("data:"):
        header, b64data = data_uri.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
    else:
        b64data = data_uri
        content_type = "image/jpeg"

    file_bytes = base64.b64decode(b64data)
    return Response(content=file_bytes, media_type=content_type)


@router.delete("/{seller_id}/media/{media_id}")
async def delete_media(seller_id: str, media_id: str, db: Session = Depends(get_db)):
    media = db.query(Media).filter(Media.id == media_id, Media.seller_id == seller_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    db.delete(media)
    db.commit()
    return {"message": "Media deleted"}


# === CUSTOMER TAGS (Starter+) ===

@router.put("/{seller_id}/customers/{customer_id}/tags")
async def update_customer_tags(seller_id: str, customer_id: str, tags: str = "", notes: str = None, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.seller_id == seller_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.tags = tags
    if notes is not None:
        customer.notes = notes
    db.commit()
    return {"message": "Customer updated"}


# === EXPORT ORDERS CSV (Starter+) ===

@router.get("/{seller_id}/orders/export")
async def export_orders_csv(seller_id: str, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not has_feature(seller.plan, "export_csv"):
        raise HTTPException(status_code=403, detail="Upgrade to Starter plan for CSV export")

    orders = db.query(Order).filter(Order.seller_id == seller_id).order_by(Order.created_at.desc()).all()
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Customer", "Phone", "Address", "Items", "Amount", "Payment", "Coupon", "Discount", "Status", "Date"])
    for o in orders:
        items = ", ".join([i.get("product_name", "?") for i in (o.items or [])])
        writer.writerow([
            o.id[:8], o.customer_name or "", o.customer_phone or "", o.customer_address or "",
            items, o.total_amount or 0, o.payment_method or "",
            getattr(o, 'coupon_code', '') or '', getattr(o, 'discount_amount', 0) or 0,
            o.status, o.created_at.isoformat() if o.created_at else "",
        ])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=orders_{seller_id[:8]}.csv"})


# === BROADCAST (Growth+) ===

class BroadcastInput(BaseModel):
    message: str

@router.post("/{seller_id}/broadcast")
async def broadcast_message(seller_id: str, data: BroadcastInput, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not has_feature(seller.plan, "broadcast"):
        raise HTTPException(status_code=403, detail="Upgrade to Growth plan for broadcast")

    from app.utils.facebook import send_message as fb_send
    customers = db.query(Customer).filter(Customer.seller_id == seller_id).all()
    sent = 0
    failed = 0
    for c in customers:
        try:
            await fb_send(c.fb_user_id, data.message, seller.fb_page_access_token)
            sent += 1
        except Exception:
            failed += 1
    return {"message": f"Broadcast sent to {sent} customers ({failed} failed)", "sent": sent, "failed": failed}


# === REPLY FROM DASHBOARD (Growth+) ===

class ReplyInput(BaseModel):
    message: str

@router.post("/{seller_id}/customers/{customer_id}/reply")
async def reply_to_customer(seller_id: str, customer_id: str, data: ReplyInput, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not has_feature(seller.plan, "dashboard_reply"):
        raise HTTPException(status_code=403, detail="Upgrade to Growth plan for dashboard reply")

    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.seller_id == seller_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from app.utils.facebook import send_message as fb_send
    await fb_send(customer.fb_user_id, data.message, seller.fb_page_access_token)

    # Save to conversation
    db.add(Conversation(seller_id=seller_id, customer_id=customer_id, sender="seller", message=data.message, intent="manual_reply"))
    db.commit()
    return {"message": "Reply sent"}


# === ANALYTICS (Growth+) ===

@router.get("/{seller_id}/analytics")
async def get_analytics(seller_id: str, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not has_feature(seller.plan, "analytics"):
        raise HTTPException(status_code=403, detail="Upgrade to Growth plan for analytics")

    from sqlalchemy import func as sqlfunc

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Revenue
    total_revenue = db.query(sqlfunc.sum(Order.total_amount)).filter(
        Order.seller_id == seller_id, Order.status != "cancelled"
    ).scalar() or 0
    month_revenue = db.query(sqlfunc.sum(Order.total_amount)).filter(
        Order.seller_id == seller_id, Order.status != "cancelled", Order.created_at >= month_ago
    ).scalar() or 0
    week_revenue = db.query(sqlfunc.sum(Order.total_amount)).filter(
        Order.seller_id == seller_id, Order.status != "cancelled", Order.created_at >= week_ago
    ).scalar() or 0

    # Orders per day (last 7 days)
    daily_orders = []
    for i in range(7):
        day_start = (now - timedelta(days=6-i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(Order).filter(
            Order.seller_id == seller_id, Order.created_at >= day_start, Order.created_at < day_end
        ).count()
        daily_orders.append({"date": day_start.strftime("%m/%d"), "orders": count})

    # Messages per day (last 7 days)
    daily_messages = []
    for i in range(7):
        day_start = (now - timedelta(days=6-i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(Conversation).filter(
            Conversation.seller_id == seller_id, Conversation.sender == "customer",
            Conversation.created_at >= day_start, Conversation.created_at < day_end
        ).count()
        daily_messages.append({"date": day_start.strftime("%m/%d"), "messages": count})

    # Top products
    top_products = []
    orders_with_items = db.query(Order).filter(Order.seller_id == seller_id, Order.status != "cancelled").all()
    product_counts = {}
    for o in orders_with_items:
        for item in (o.items or []):
            name = item.get("product_name", "Unknown")
            product_counts[name] = product_counts.get(name, 0) + 1
    for name, count in sorted(product_counts.items(), key=lambda x: -x[1])[:5]:
        top_products.append({"name": name, "orders": count})

    return {
        "revenue": {"total": total_revenue, "month": month_revenue, "week": week_revenue},
        "daily_orders": daily_orders,
        "daily_messages": daily_messages,
        "top_products": top_products,
        "total_orders": db.query(Order).filter(Order.seller_id == seller_id).count(),
        "total_customers": db.query(Customer).filter(Customer.seller_id == seller_id).count(),
    }


# === COUPONS (Growth+) ===

class CouponCreate(BaseModel):
    code: str
    discount_type: str = "percentage"
    discount_value: float
    min_order: float = 0
    max_uses: int = -1

@router.get("/{seller_id}/coupons")
async def get_coupons(seller_id: str, db: Session = Depends(get_db)):
    coupons = db.query(Coupon).filter(Coupon.seller_id == seller_id).order_by(Coupon.created_at.desc()).all()
    return [{
        "id": c.id, "code": c.code, "discount_type": c.discount_type,
        "discount_value": c.discount_value, "min_order": c.min_order,
        "max_uses": c.max_uses, "used_count": c.used_count, "is_active": c.is_active,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
    } for c in coupons]

@router.post("/{seller_id}/coupons")
async def create_coupon(seller_id: str, data: CouponCreate, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not has_feature(seller.plan, "coupons"):
        raise HTTPException(status_code=403, detail="Upgrade to Growth plan for coupons")

    coupon = Coupon(
        seller_id=seller_id, code=data.code.upper(),
        discount_type=data.discount_type, discount_value=data.discount_value,
        min_order=data.min_order, max_uses=data.max_uses,
    )
    db.add(coupon)
    db.commit()
    return {"id": coupon.id, "message": f"Coupon {coupon.code} created"}

@router.delete("/{seller_id}/coupons/{coupon_id}")
async def delete_coupon(seller_id: str, coupon_id: str, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id, Coupon.seller_id == seller_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
    return {"message": "Coupon deleted"}


# === PLAN INFO ===

@router.get("/{seller_id}/plan-info")
async def get_plan_info(seller_id: str, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    plan = seller.plan or "trial"
    features = PLAN_FEATURES.get(plan, PLAN_FEATURES["trial"])["features"]
    return {
        "current_plan": plan,
        "features": features,
        "plans": {k: {"price_bdt": v["price_bdt"], "features": v["features"]} for k, v in PLAN_FEATURES.items()},
    }


# === FOLLOW-UP CRON (Starter+) ===

@router.get("/{seller_id}/cron/followup")
async def cron_followup(seller_id: str, db: Session = Depends(get_db)):
    """Send follow-up messages for orders placed 24+ hours ago."""
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller or not has_feature(seller.plan, "auto_followup"):
        return {"message": "Feature not available"}

    from app.utils.facebook import send_message as fb_send
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    orders = db.query(Order).filter(
        Order.seller_id == seller_id,
        Order.followed_up == False,
        Order.status == "confirmed",
        Order.created_at <= cutoff,
    ).limit(10).all()

    sent = 0
    for o in orders:
        customer = db.query(Customer).filter(Customer.id == o.customer_id).first()
        if customer:
            msg = f"Hi {customer.name or 'there'}! Your order #{o.id[:8]} is confirmed and being prepared. We'll update you when it ships. Thanks for shopping with {seller.fb_page_name}!"
            try:
                await fb_send(customer.fb_user_id, msg, seller.fb_page_access_token)
                o.followed_up = True
                sent += 1
            except Exception as e:
                print(f"Follow-up failed: {e}")
    db.commit()
    return {"message": f"Sent {sent} follow-ups"}
