"""
Facebook Messenger Webhook — Receives messages from customers and sends AI replies.
"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime
from datetime import datetime, timezone

from app.config import settings
from app.models.database import get_db, Base, engine
from app.models.models import Seller, Customer, Product, Media
from app.services.ai_agent import get_ai_response
from app.utils.facebook import (
    send_message,
    send_typing_indicator,
    send_product_cards,
    send_private_reply,
    send_media_message,
    get_user_profile,
    verify_webhook_signature,
)


# Track processed message IDs to prevent duplicate replies
class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    mid = Column(String, primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.fb_verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if signature and not verify_webhook_signature(body, signature):
        print(f"Signature mismatch - got: {signature[:30]}...")

    data = await request.json()

    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", []):
        page_id = entry.get("id")

        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or not message.get("text"):
                continue
            if message.get("is_echo"):
                continue

            # Deduplication
            mid = message.get("mid")
            if mid:
                existing = db.query(ProcessedMessage).filter(ProcessedMessage.mid == mid).first()
                if existing:
                    continue
                db.add(ProcessedMessage(mid=mid))
                db.commit()

            sender_id = event["sender"]["id"]
            message_text = message["text"]

            await handle_customer_message(db, page_id, sender_id, message_text)

        # Handle comments on posts (feed webhook)
        for change in entry.get("changes", []):
            if change.get("field") != "feed":
                continue
            value = change.get("value", {})
            if value.get("item") != "comment" or value.get("verb") != "add":
                continue
            # Skip page's own comments and replies created by the app
            commenter_id = value.get("from", {}).get("id", "")
            if commenter_id == page_id:
                continue
            # Skip replies to comments (only respond to top-level)
            if value.get("parent_id"):
                continue
                comment_id = value.get("comment_id")
                if comment_id:
                    # Dedup comments too
                    existing = db.query(ProcessedMessage).filter(ProcessedMessage.mid == f"comment_{comment_id}").first()
                    if existing:
                        continue
                    db.add(ProcessedMessage(mid=f"comment_{comment_id}"))
                    db.commit()

                    await handle_comment(db, page_id, value)

    return {"status": "ok"}


async def handle_comment(db: Session, page_id: str, value: dict):
    """When someone comments on a post, send them a private DM via Messenger."""
    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        return

    comment_id = value.get("comment_id")
    comment_text = value.get("message", "").strip()
    commenter_name = value.get("from", {}).get("name", "")
    post_id = value.get("post_id", "")

    # Find matching product from the post
    product_info = ""
    if post_id:
        product = db.query(Product).filter(
            Product.seller_id == seller.id,
            Product.fb_post_id == post_id,
            Product.is_available == True,
        ).first()
        if product:
            product_info = f"\n\nProduct: {product.name}"
            if product.price_text or product.price:
                product_info += f"\nPrice: {product.price_text or str(product.price) + ' BDT'}"

    # Build a friendly DM
    dm_text = (
        f"Hi {commenter_name}! {seller.fb_page_name} এ আপনার comment দেখেছি। "
        f"ধন্যবাদ!"
    )
    if product_info:
        dm_text += product_info
    dm_text += "\n\nকোনো প্রশ্ন থাকলে এখানে message করুন, আমি সাহায্য করব!"

    try:
        await send_private_reply(comment_id, dm_text, seller.fb_page_access_token)
    except Exception as e:
        print(f"Comment auto-DM failed: {e}")


async def handle_customer_message(db: Session, page_id: str, sender_id: str, message_text: str):
    """Process a single customer message and send AI response."""

    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        print(f"No seller found for page {page_id}")
        return

    await send_typing_indicator(sender_id, seller.fb_page_access_token)

    customer = db.query(Customer).filter(
        Customer.seller_id == seller.id,
        Customer.fb_user_id == sender_id,
    ).first()

    if not customer:
        profile = await get_user_profile(sender_id, seller.fb_page_access_token)
        customer = Customer(
            seller_id=seller.id,
            fb_user_id=sender_id,
            name=f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    try:
        result = get_ai_response(db, seller, customer, message_text)
    except Exception as e:
        print(f"AI error: {e}")
        result = {
            "reply": "একটু wait করুন, আপনাকে শীঘ্রই reply দেওয়া হবে। ধন্যবাদ!",
            "needs_human": True,
        }

    # Send AI reply
    reply_text = result.get("reply", "")
    if reply_text:
        await send_message(sender_id, reply_text, seller.fb_page_access_token)

    # Send product cards with images if AI requested
    show_products = result.get("show_products")
    if show_products:
        products = db.query(Product).filter(
            Product.seller_id == seller.id,
            Product.is_available == True,
        ).all()
        cards = []
        for idx in show_products:
            if 1 <= idx <= len(products):
                p = products[idx - 1]
                cards.append({
                    "name": p.name,
                    "price": p.price_text or (f"{p.price} BDT" if p.price else ""),
                    "image_url": p.image_url,
                })
        if cards:
            await send_product_cards(sender_id, cards, seller.fb_page_access_token)

    # Send media if AI requested
    send_media_ids = result.get("send_media")
    if send_media_ids:
        media_list = db.query(Media).filter(
            Media.seller_id == seller.id,
        ).all()
        for idx in send_media_ids:
            if 1 <= idx <= len(media_list):
                m = media_list[idx - 1]
                await send_media_message(sender_id, m.url, m.media_type, seller.fb_page_access_token)

    # If a new order was created, send confirmation + notify seller
    new_order = result.get("new_order")
    if new_order:
        # Send order confirmation to customer
        confirmation = (
            f"✅ আপনার Order Confirm হয়েছে!\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📋 Order ID: #{new_order['id']}\n"
            f"📦 Product: {new_order['product']}\n"
            f"👤 নাম: {new_order['customer_name']}\n"
            f"📱 Phone: {new_order['phone']}\n"
            f"📍 Address: {new_order['address']}\n"
            f"💳 Payment: {new_order['payment_method']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"আমরা শীঘ্রই আপনার order process করব। ধন্যবাদ!"
        )
        await send_message(sender_id, confirmation, seller.fb_page_access_token)

        # Notify seller (send to page's admin via page conversation)
        await notify_seller_new_order(seller, customer, new_order)

    # Log if needs human
    if result.get("needs_human"):
        print(f"[NEEDS ATTENTION] Customer: {customer.name or sender_id} | Message: {message_text}")


async def notify_seller_new_order(seller: Seller, customer: Customer, order: dict):
    """Send order notification to seller's admin."""
    # If seller has admin_fb_user_id, notify them directly
    admin_id = getattr(seller, 'admin_fb_user_id', None)
    if not admin_id:
        print(f"[NEW ORDER] #{order['id']} | {order['product']} | {order['customer_name']} | {order['phone']}")
        return

    notification = (
        f"🔔 নতুন Order এসেছে!\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 Order ID: #{order['id']}\n"
        f"📦 Product: {order['product']}\n"
        f"👤 Customer: {order['customer_name']}\n"
        f"📱 Phone: {order['phone']}\n"
        f"📍 Address: {order['address']}\n"
        f"💳 Payment: {order['payment_method']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Order confirm করতে dashboard এ যান।"
    )

    try:
        await send_message(admin_id, notification, seller.fb_page_access_token)
    except Exception as e:
        print(f"Failed to notify seller: {e}")
