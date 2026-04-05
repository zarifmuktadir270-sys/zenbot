"""
AI Agent — The brain of the chatbot.
Uses Claude to understand customer messages and respond intelligently.
"""

import json
from typing import List
import anthropic
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Seller, Product, Customer, Conversation, Order

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def build_system_prompt(seller: Seller, products: List[Product]) -> str:
    """Build the AI system prompt with seller's shop info and products."""

    # Format product catalog from scraped Facebook posts
    product_list = ""
    for p in products:
        if p.is_available:
            product_list += f"- {p.name}"
            if p.price:
                product_list += f" | Price: {p.price_text or str(p.price) + ' BDT'}"
            if p.description:
                product_list += f" | Details: {p.description[:200]}"
            product_list += "\n"

    if not product_list:
        product_list = "No products loaded yet. Ask the customer to describe what they want and you'll check with the shop owner."

    return f"""You are the customer service assistant for "{seller.fb_page_name}", a shop on Facebook.
You chat with customers on Messenger. Be friendly, helpful, and conversational.

## YOUR RULES:
1. Reply in the SAME LANGUAGE the customer uses. If they write Bangla, reply in Bangla. If Banglish (Bangla in English letters), reply in Banglish. If English, reply in English.
2. Keep replies SHORT — 1-3 sentences max. Customers are on mobile.
3. NEVER make up information. Only share what you know from the product list and shop info below.
4. If you don't know something, say "Apni ektu wait korun, shop owner ke jigges kore janacchi" (or equivalent in their language).
5. When a customer wants to ORDER, collect: (a) product name/details, (b) full name, (c) phone number, (d) delivery address, (e) payment method. Collect one or two at a time, don't dump all questions at once.
6. You are NOT human. If asked, say you are an AI assistant for the shop.
7. Be warm and use common BD greetings like "vai", "apu", "ji" naturally.

## SHOP INFORMATION:
- Shop Name: {seller.fb_page_name}
- Delivery Charges: {seller.delivery_info}
- Payment Methods: {seller.payment_methods}
- Delivery Time: {seller.delivery_time}
- Return Policy: {seller.return_policy}

## PRODUCT CATALOG:
{product_list}

## HOW TO RESPOND:
Always respond with a JSON object (and nothing else):
{{
  "reply": "your message to the customer",
  "intent": "inquiry|order|complaint|tracking|greeting|general",
  "order_data": null or {{"product": "...", "customer_name": "...", "phone": "...", "address": "...", "payment_method": "...", "notes": "..."}},
  "needs_human": false or true
}}

- Set "needs_human" to true ONLY for: complaints, custom/bulk orders, issues you can't resolve.
- Set "order_data" when you have collected ALL order details from the customer. Fill only the fields you have so far, leave others as null.
- For "intent": use "order" when customer is in the process of ordering.

Today's date: {datetime.now(timezone.utc).strftime("%Y-%m-%d %A")}
"""


def get_conversation_history(db: Session, seller_id: str, customer_id: str, limit: int = 20) -> List[dict]:
    """Get recent conversation history formatted for Claude."""
    messages = (
        db.query(Conversation)
        .filter(Conversation.seller_id == seller_id, Conversation.customer_id == customer_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )
    messages.reverse()  # Oldest first

    formatted = []
    for msg in messages:
        role = "user" if msg.sender == "customer" else "assistant"
        content = msg.message
        # For assistant messages, wrap in JSON format as Claude expects
        if role == "assistant":
            content = json.dumps({"reply": content, "intent": msg.intent or "general", "order_data": None, "needs_human": False})
        formatted.append({"role": role, "content": content})

    return formatted


def get_ai_response(db: Session, seller: Seller, customer: Customer, message: str) -> dict:
    """
    Process a customer message and get AI response.
    Returns: {"reply": str, "intent": str, "order_data": dict|None, "needs_human": bool}
    """

    # Load seller's products
    products = db.query(Product).filter(Product.seller_id == seller.id).all()

    # Build system prompt
    system_prompt = build_system_prompt(seller, products)

    # Get conversation history
    history = get_conversation_history(db, seller.id, customer.id)

    # Add current message
    history.append({"role": "user", "content": message})

    # Deduplicate consecutive same-role messages (Claude API requirement)
    cleaned = []
    for msg in history:
        if cleaned and cleaned[-1]["role"] == msg["role"]:
            cleaned[-1]["content"] += "\n" + msg["content"]
        else:
            cleaned.append(msg)

    # Ensure conversation starts with "user" role
    if cleaned and cleaned[0]["role"] != "user":
        cleaned = cleaned[1:]

    # Call Claude
    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=300,
        system=system_prompt,
        messages=cleaned,
    )

    # Parse response
    raw_text = response.content[0].text.strip()

    # Try to parse as JSON
    try:
        # Handle cases where Claude wraps JSON in markdown code blocks
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)
    except json.JSONDecodeError:
        # If Claude didn't return JSON, use the raw text as reply
        result = {
            "reply": raw_text,
            "intent": "general",
            "order_data": None,
            "needs_human": False,
        }

    # Save conversation to database
    # Save customer message
    db.add(Conversation(
        seller_id=seller.id,
        customer_id=customer.id,
        sender="customer",
        message=message,
        intent=result.get("intent", "general"),
    ))

    # Save agent reply
    db.add(Conversation(
        seller_id=seller.id,
        customer_id=customer.id,
        sender="agent",
        message=result.get("reply", ""),
        intent=result.get("intent", "general"),
    ))

    # If order data is complete, create an order
    order_data = result.get("order_data")
    if order_data and all(order_data.get(f) for f in ["product", "customer_name", "phone", "address"]):
        order = Order(
            seller_id=seller.id,
            customer_id=customer.id,
            items=[{"product_name": order_data["product"], "quantity": 1}],
            customer_name=order_data["customer_name"],
            customer_phone=order_data["phone"],
            customer_address=order_data["address"],
            payment_method=order_data.get("payment_method", "COD"),
            notes=order_data.get("notes", ""),
            status="pending",
        )
        db.add(order)

        # Update customer info
        customer.name = order_data["customer_name"]
        customer.phone = order_data["phone"]
        customer.address = order_data["address"]
        customer.total_orders = (customer.total_orders or 0) + 1

    db.commit()

    return result
