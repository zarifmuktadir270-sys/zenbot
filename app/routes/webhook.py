"""
Facebook Messenger Webhook — Receives messages from customers and sends AI replies.
"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime
from datetime import datetime, timezone

from app.config import settings
from app.models.database import get_db, Base, engine
from app.models.models import Seller, Customer, Product, Media, Order, has_feature
from app.services.ai_agent import get_ai_response
from app.utils.facebook import (
    send_message,
    send_typing_indicator,
    send_product_cards,
    send_private_reply,
    send_media_message,
    send_quick_replies,
    get_user_profile,
    verify_webhook_signature,
)


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
    import traceback
    try:
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
                if not message:
                    continue
                if message.get("is_echo"):
                    continue

                mid = message.get("mid")
                if mid:
                    existing = db.query(ProcessedMessage).filter(ProcessedMessage.mid == mid).first()
                    if existing:
                        continue
                    db.add(ProcessedMessage(mid=mid))
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()

                sender_id = event["sender"]["id"]

                if not message.get("text"):
                    try:
                        await handle_non_text_message(db, page_id, sender_id, message)
                    except Exception as e:
                        print(f"Non-text handler error: {e}")
                    continue

                message_text = message["text"]
                try:
                    await handle_customer_message(db, page_id, sender_id, message_text)
                except Exception as e:
                    print(f"MESSAGE HANDLER ERROR: {traceback.format_exc()}")

            # Handle comments on posts
            for change in entry.get("changes", []):
                if change.get("field") != "feed":
                    continue
                value = change.get("value", {})
                if value.get("item") != "comment" or value.get("verb") != "add":
                    continue
                commenter_id = value.get("from", {}).get("id", "")
                if commenter_id == page_id:
                    continue
                if value.get("parent_id"):
                    continue
                comment_id = value.get("comment_id")
                if comment_id:
                    existing = db.query(ProcessedMessage).filter(ProcessedMessage.mid == f"comment_{comment_id}").first()
                    if existing:
                        continue
                    db.add(ProcessedMessage(mid=f"comment_{comment_id}"))
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                    try:
                        await handle_comment(db, page_id, value)
                    except Exception as e:
                        print(f"Comment handler error: {e}")

    except Exception as e:
        print(f"WEBHOOK FATAL ERROR: {traceback.format_exc()}")

    return {"status": "ok"}


# === COMMENT AUTO-REPLY ===
async def handle_comment(db: Session, page_id: str, value: dict):
    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        return

    comment_id = value.get("comment_id")
    comment_text = value.get("message", "").strip()
    commenter_name = value.get("from", {}).get("name", "")
    post_id = value.get("post_id", "")

    product = None
    if post_id:
        product = db.query(Product).filter(
            Product.seller_id == seller.id,
            Product.fb_post_id == post_id,
            Product.is_available == True,
        ).first()

    # Build smart auto-reply based on comment content
    dm_text = f"Hi {commenter_name}! Thanks for your interest in {seller.fb_page_name}!"
    if product:
        dm_text += f"\n\nProduct: {product.name}"
        if product.price_text or product.price:
            dm_text += f"\nPrice: {product.price_text or str(int(product.price)) + ' BDT'}"
        if product.stock is not None and product.stock == 0:
            dm_text += "\n(Currently out of stock)"
        else:
            dm_text += "\nThis item is available!"
    dm_text += "\n\nMessage me here if you want to order or have any questions!"

    try:
        await send_private_reply(comment_id, dm_text, seller.fb_page_access_token)
    except Exception as e:
        print(f"Comment auto-DM failed: {e}")


async def handle_non_text_message(db: Session, page_id: str, sender_id: str, message: dict):
    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        return

    attachments = message.get("attachments", [])
    if not attachments:
        return

    msg_type = attachments[0].get("type", "media")

    replies = {
        "audio": "Sorry, I can't listen to voice messages yet. Please type your message instead!",
        "image": "Got your photo! What product are you asking about? Please type it out.",
        "video": "Got your video! Please type your question and I'll help you.",
        "file": "Got your file! How can I help you?",
    }
    reply = replies.get(msg_type, "I can only reply to text messages. Please type your question!")
    await send_message(sender_id, reply, seller.fb_page_access_token)


# === MAIN MESSAGE HANDLER ===
async def handle_customer_message(db: Session, page_id: str, sender_id: str, message_text: str):
    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        return

    if not seller.is_active:
        return

    if seller.bot_paused:
        return

    now = datetime.now(timezone.utc)
    plan_exp = seller.plan_expires_at
    if plan_exp and plan_exp.tzinfo is None:
        plan_exp = plan_exp.replace(tzinfo=timezone.utc)
    if plan_exp and now > plan_exp:
        await send_message(
            sender_id,
            "Sorry, this shop's subscription has expired. Please contact the shop owner directly. Thanks!",
            seller.fb_page_access_token
        )
        return

    await send_typing_indicator(sender_id, seller.fb_page_access_token)

    # Get or create customer
    customer = db.query(Customer).filter(
        Customer.seller_id == seller.id,
        Customer.fb_user_id == sender_id,
    ).first()

    is_new_customer = False
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
        is_new_customer = True

    # === WELCOME MESSAGE (Trial+) ===
    if is_new_customer or not getattr(customer, 'is_welcomed', False):
        welcome = getattr(seller, 'welcome_message', '') or ''
        if welcome:
            await send_message(sender_id, welcome, seller.fb_page_access_token)
            customer.is_welcomed = True
            db.commit()

    # === ORDER TRACKING (Trial+) ===
    lower_msg = message_text.lower().strip()
    if any(kw in lower_msg for kw in ['order status', 'track order', 'order track', 'my order', 'amar order', 'order ki holo']):
        await handle_order_tracking(db, seller, customer, sender_id)
        return

    # === AI RESPONSE ===
    try:
        result = get_ai_response(db, seller, customer, message_text)
    except Exception as e:
        print(f"AI error: {e}")
        result = {
            "reply": "Please wait, someone will reply to you shortly. Thanks!",
            "needs_human": True,
        }

    # Send AI reply — ensure no raw JSON
    reply_text = result.get("reply", "")
    if reply_text:
        reply_text = reply_text.strip()
        if reply_text.startswith("{") or reply_text.startswith("["):
            import json as _json, re as _re
            try:
                parsed = _json.loads(reply_text)
                if isinstance(parsed, dict) and "reply" in parsed:
                    reply_text = parsed["reply"]
            except:
                m = _re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', reply_text)
                if m:
                    reply_text = m.group(1).replace('\\"', '"').replace('\\n', '\n')
                else:
                    reply_text = "Sorry, something went wrong. Please message again!"

    # === QUICK REPLY BUTTONS (Trial+) ===
    if has_feature(seller.plan, "quick_replies") and result.get("intent") in ("greeting", "general"):
        quick = ["View Products", "Track Order", "Contact Owner"]
        await send_quick_replies(sender_id, reply_text, quick, seller.fb_page_access_token)
    elif reply_text:
        await send_message(sender_id, reply_text, seller.fb_page_access_token)

    # Send product cards
    show_products = result.get("show_products")
    if show_products and isinstance(show_products, list):
        products = db.query(Product).filter(
            Product.seller_id == seller.id, Product.is_available == True,
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

    # Send media
    send_media_ids = result.get("send_media")
    if send_media_ids and isinstance(send_media_ids, list):
        media_list = db.query(Media).filter(Media.seller_id == seller.id).all()
        for idx in send_media_ids:
            if 1 <= idx <= len(media_list):
                m = media_list[idx - 1]
                await send_media_message(sender_id, m.url, m.media_type, seller.fb_page_access_token)

    # Order created — send confirmation
    new_order = result.get("new_order")
    if new_order:
        confirmation = (
            f"Order Confirmed!\n"
            f"-------------------\n"
            f"Order ID: #{new_order['id']}\n"
            f"Product: {new_order['product']}\n"
            f"Name: {new_order['customer_name']}\n"
            f"Phone: {new_order['phone']}\n"
            f"Address: {new_order['address']}\n"
            f"Payment: {new_order['payment_method']}\n"
            f"-------------------\n"
            f"We'll process your order soon. Thanks!"
        )
        await send_message(sender_id, confirmation, seller.fb_page_access_token)
        await notify_seller_new_order(seller, customer, new_order)

    if result.get("needs_human"):
        print(f"[NEEDS ATTENTION] {customer.name or sender_id}: {message_text}")


# === ORDER TRACKING ===
async def handle_order_tracking(db: Session, seller: Seller, customer: Customer, sender_id: str):
    orders = db.query(Order).filter(
        Order.seller_id == seller.id,
        Order.customer_id == customer.id,
    ).order_by(Order.created_at.desc()).limit(3).all()

    if not orders:
        await send_message(sender_id, "You don't have any orders yet. Want to browse our products?", seller.fb_page_access_token)
        return

    status_text = {
        "pending": "Pending (waiting for confirmation)",
        "confirmed": "Confirmed (being prepared)",
        "shipped": "Shipped (on the way!)",
        "delivered": "Delivered",
        "cancelled": "Cancelled",
    }

    msg = "Your recent orders:\n"
    for o in orders:
        items = ", ".join([i.get("product_name", "?") for i in (o.items or [])]) or "N/A"
        s = status_text.get(o.status, o.status)
        msg += f"\n#{o.id[:8]} - {items}\nStatus: {s}\n"

    await send_message(sender_id, msg, seller.fb_page_access_token)


# === SELLER NOTIFICATION ===
async def notify_seller_new_order(seller: Seller, customer: Customer, order: dict):
    admin_id = getattr(seller, 'admin_fb_user_id', None)
    if not admin_id:
        print(f"[NEW ORDER] #{order['id']} | {order['product']} | {order['customer_name']}")
        return

    notification = (
        f"NEW ORDER!\n"
        f"-------------------\n"
        f"Order ID: #{order['id']}\n"
        f"Product: {order['product']}\n"
        f"Customer: {order['customer_name']}\n"
        f"Phone: {order['phone']}\n"
        f"Address: {order['address']}\n"
        f"Payment: {order['payment_method']}\n"
        f"-------------------\n"
        f"Go to dashboard to confirm."
    )

    try:
        await send_message(admin_id, notification, seller.fb_page_access_token)
    except Exception as e:
        print(f"Failed to notify seller: {e}")
