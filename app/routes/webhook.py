"""
Facebook Messenger Webhook — Receives messages from customers and sends AI replies.
This is the CORE of the chatbot.
"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import get_db
from app.models.models import Seller, Customer
from app.services.ai_agent import get_ai_response
from app.utils.facebook import (
    send_message,
    send_typing_indicator,
    get_user_profile,
    verify_webhook_signature,
)

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    STEP 1 of Messenger setup: Facebook sends a GET request to verify your webhook.
    You must return the challenge token if the verify_token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.fb_verify_token:
        print(f"Webhook verified successfully!")
        return int(hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """
    STEP 2: Facebook sends POST requests here whenever a customer messages your page.
    Flow: Customer Message → This Webhook → AI Agent → Reply via Messenger API
    """
    # Verify the request is from Facebook
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()

    # Facebook sends different types of events — we only care about messages
    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", []):
        page_id = entry.get("id")

        for event in entry.get("messaging", []):
            # Skip if not a text message (could be delivery receipt, read receipt, etc.)
            message = event.get("message")
            if not message or not message.get("text"):
                continue

            # Skip echo messages (messages sent BY the page, not TO it)
            if message.get("is_echo"):
                continue

            sender_id = event["sender"]["id"]
            message_text = message["text"]

            # Process the message
            await handle_customer_message(db, page_id, sender_id, message_text)

    return {"status": "ok"}


async def handle_customer_message(db: Session, page_id: str, sender_id: str, message_text: str):
    """Process a single customer message and send AI response."""

    # 1. Find the seller by their Facebook page ID
    seller = db.query(Seller).filter(Seller.fb_page_id == page_id).first()
    if not seller:
        print(f"No seller found for page {page_id}")
        return

    # 2. Show typing indicator (so customer knows we're processing)
    await send_typing_indicator(sender_id, seller.fb_page_access_token)

    # 3. Find or create customer
    customer = db.query(Customer).filter(
        Customer.seller_id == seller.id,
        Customer.fb_user_id == sender_id,
    ).first()

    if not customer:
        # New customer — get their name from Facebook
        profile = await get_user_profile(sender_id, seller.fb_page_access_token)
        customer = Customer(
            seller_id=seller.id,
            fb_user_id=sender_id,
            name=f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # 4. Get AI response
    try:
        result = get_ai_response(db, seller, customer, message_text)
    except Exception as e:
        print(f"AI error: {e}")
        # Fallback message if AI fails
        result = {
            "reply": "Ektu wait korun, amra apnake shighroi reply dibo. Dhonnobad!",
            "needs_human": True,
        }

    # 5. Send reply to customer
    reply_text = result.get("reply", "")
    if reply_text:
        await send_message(sender_id, reply_text, seller.fb_page_access_token)

    # 6. If needs human intervention, notify the seller
    if result.get("needs_human"):
        seller_notification = (
            f"[NEEDS ATTENTION]\n"
            f"Customer: {customer.name or sender_id}\n"
            f"Message: {message_text}\n"
            f"AI Reply: {reply_text}\n"
            f"---\nReply directly on Messenger to take over."
        )
        # You could send this via WhatsApp, SMS, or email to the seller
        print(seller_notification)  # For now, just log it
