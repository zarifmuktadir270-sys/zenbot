"""
AI Agent — The brain of the chatbot.
Uses Kilo Gateway (OpenAI-compatible) to understand customer messages and respond intelligently.
"""

import json
from typing import List
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Seller, Product, Customer, Conversation, Order, Media

KILO_BASE_URL = "https://api.kilo.ai/api/gateway"
KILO_MODELS = [
    "bytedance-seed/dola-seed-2.0-pro:free",
    "qwen/qwen3.6-plus:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "arcee-ai/trinity-large-preview:free",
]


def build_system_prompt(seller: Seller, products: List[Product], media_list: List[Media] = None) -> str:
    """Build the AI system prompt with seller's shop info and products."""

    bot_name = getattr(seller, "bot_name", "") or "AI Assistant"

    # Format product catalog
    product_list = ""
    for i, p in enumerate(products):
        if p.is_available:
            product_list += f"- [{i+1}] {p.name}"
            if p.price:
                product_list += f" | Price: {p.price_text or str(p.price) + ' BDT'}"
            if p.description:
                product_list += f" | Details: {p.description[:150]}"
            if p.image_url:
                product_list += f" | HAS_IMAGE"
            # Show stock info
            if p.stock is not None and p.stock >= 0:
                if p.stock == 0:
                    product_list += f" | OUT OF STOCK"
                else:
                    product_list += f" | Stock: {p.stock} units"
            product_list += "\n"

    if not product_list:
        product_list = "No products loaded yet."

    # Format media
    media_section = ""
    if media_list:
        media_section = "\n## MEDIA FILES (you can send these):\n"
        for i, m in enumerate(media_list):
            media_section += f"- [M{i+1}] {m.name} ({m.media_type}) | tags: {m.tags}\n"
        media_section += "\nTo send media, include \"send_media\": [1, 2] in your response.\n"

    # Custom instructions & learned knowledge
    custom_section = ""
    custom_inst = getattr(seller, "custom_instructions", "") or ""
    learned = getattr(seller, "learned_knowledge", "") or ""
    if custom_inst:
        custom_section += f"\n## OWNER'S INSTRUCTIONS (follow these strictly):\n{custom_inst}\n"
    if learned:
        custom_section += f"\n## LEARNED KNOWLEDGE (owner taught you these):\n{learned}\nIMPORTANT: Only mention knowledge that is DIRECTLY relevant to the customer's current question. Do NOT dump all knowledge at once.\n"

    return f"""You are "{bot_name}", the AI assistant for "{seller.fb_page_name}" on Facebook Messenger. You talk to customers like a friendly, helpful shop person — not like a robot or a corporate helpdesk.

## TONE & PERSONALITY (VERY IMPORTANT):
- Talk like a real person running a small shop in Bangladesh. Warm, casual, helpful.
- Use "তুমি" or "আপনি" based on how the customer talks to you. If they're casual, you be casual.
- Keep it conversational — like you're chatting with a friend who walked into your shop.
- DON'T sound robotic, stiff, or overly formal. No "আমাদের প্রতিষ্ঠানে আপনাকে স্বাগতম" type cringe.
- It's okay to be a bit playful. Use "ভাই/আপু/sis/bro" if the vibe fits.
- Show enthusiasm when someone wants to buy something.

## LANGUAGE STYLE:
- Bangla sentences with English terms mixed in naturally — the way people actually talk in BD.
- Keep English words in English: brand names, product names, order, delivery, confirm, cancel, size, color, stock, available, bKash, Nagad, COD, etc.
- Write Bangla parts in proper Bangla script (NOT Banglish/Roman letters).
- Good examples:
  - "জি ভাই, এটা available আছে! কোন size লাগবে?"
  - "দাম ৮৫০ টাকা, delivery charge ঢাকায় ৬০। Order দিবেন?"
  - "নাম আর phone number টা দেন, order process করে দিচ্ছি।"
  - "ওহ এটা just sold out হয়ে গেছে! অন্য কিছু দেখবেন?"
- BAD examples (never do these):
  - "apni ki order korte chan?" (Banglish — ugly)
  - "আমাদের shop এ আপনাকে স্বাগত জানাচ্ছি। আপনি কি কিছু order করতে আগ্রহী?" (too formal/robotic)
  - Full English paragraphs (customers prefer Bangla mix)

## RULES:
1. Keep replies SHORT — 1-3 lines max. Customers are on mobile. Nobody reads paragraphs.
2. Never make up info. Only use the product list and shop info below.
3. যা জানো না, সোজা বলো: "এটা আমি sure না, owner কে জিজ্ঞেস করে জানাচ্ছি!"
4. For orders, collect info naturally (don't sound like a form):
   - First: কোন product চান
   - Then: নাম আর phone number
   - Then: delivery address
   - Last: payment method
5. If someone asks if you're a bot, be honest: "জি, আমি এই shop এর AI assistant। তবে help করতে পারব!"
6. Max 1-2 emojis per message. Don't overdo it.
7. Check product stock before confirming. If out of stock, let them know and suggest alternatives.
8. Only share what's relevant to their question. Don't dump everything at once.

## SHOP INFO:
- Shop: {seller.fb_page_name}
- Delivery charge: {seller.delivery_info}
- Payment: {seller.payment_methods}
- Delivery time: {seller.delivery_time}
- Return policy: {seller.return_policy}

## PRODUCTS:
{product_list}
{media_section}{custom_section}
## RESPONSE FORMAT:
Always respond with ONLY this JSON (nothing else):
{{
  "reply": "your message to customer in Bangla+English mix",
  "intent": "inquiry|order|complaint|tracking|greeting|general",
  "show_products": null,
  "send_media": null,
  "order_data": null,
  "needs_human": false
}}

## WHEN TO SHOW PRODUCTS (show_products field):
ONLY set "show_products": [1, 2, 3] when customer EXPLICITLY asks to see products:
- "ki ache?" / "what do you have?"
- "product gula dekhao" / "show me products"
- "kono design ache?" / "do you have any designs?"
- When they ask to see a SPECIFIC product by name and you found it in the list

DO NOT show products when:
- Customer just says hi/hello/greeting
- They ask about price/delivery/payment (just answer in text)
- They're placing an order (already know what they want)
- They ask a general question
- Default should ALWAYS be null

Example: Customer says "hello" → show_products: null
Example: Customer says "ki ache?" → show_products: [1, 2, 3] (show first 3)
Example: Customer says "price koto?" → show_products: null (answer in text only)

Today: {datetime.now(timezone.utc).strftime("%Y-%m-%d %A")}
"""


def get_conversation_history(db: Session, seller_id: str, customer_id: str, limit: int = 20) -> List[dict]:
    """Get recent conversation history formatted for the AI."""
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
        # For assistant messages, wrap in JSON format
        if role == "assistant":
            content = json.dumps({
                "reply": content,
                "intent": msg.intent or "general",
                "show_products": None,  # Always null in history to prevent repeating
                "send_media": None,
                "order_data": None,
                "needs_human": False
            })
        formatted.append({"role": role, "content": content})

    return formatted


def get_ai_response(db: Session, seller: Seller, customer: Customer, message: str) -> dict:
    """
    Process a customer message and get AI response via Kilo Gateway.
    Returns: {"reply": str, "intent": str, "order_data": dict|None, "needs_human": bool}
    """

    # Load seller's products and media
    products = db.query(Product).filter(Product.seller_id == seller.id).all()
    media_list = db.query(Media).filter(Media.seller_id == seller.id).all()

    # Build system prompt
    system_prompt = build_system_prompt(seller, products, media_list)

    # Get conversation history
    history = get_conversation_history(db, seller.id, customer.id)

    # Add current message
    history.append({"role": "user", "content": message})

    # Deduplicate consecutive same-role messages
    cleaned = []
    for msg in history:
        if cleaned and cleaned[-1]["role"] == msg["role"]:
            cleaned[-1]["content"] += "\n" + msg["content"]
        else:
            cleaned.append(msg)

    # Ensure conversation starts with "user" role
    if cleaned and cleaned[0]["role"] != "user":
        cleaned = cleaned[1:]

    # Add system message at the beginning
    messages = [{"role": "system", "content": system_prompt}] + cleaned

    # Call Kilo Gateway (OpenAI-compatible) — try models with fallback
    import time
    data = None
    with httpx.Client(timeout=30) as http_client:
        for attempt, model in enumerate(KILO_MODELS):
            try:
                response = http_client.post(
                    f"{KILO_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.kilo_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 500,  # Increased to prevent response cutoff
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                resp_data = response.json()
                # Verify response has content
                content = resp_data.get("choices", [{}])[0].get("message", {}).get("content")
                if not content:
                    print(f"Model {model} returned empty, trying next...")
                    continue
                data = resp_data
                break
            except httpx.HTTPStatusError as e:
                print(f"Model {model} failed ({e.response.status_code}), trying next...")
                if attempt == 0:
                    time.sleep(1)  # Brief pause before trying next
                continue
            except Exception as e:
                print(f"Model {model} error: {e}, trying next...")
                continue
        if data is None:
            raise Exception("All AI models are unavailable")

    # Extract response text
    raw_text = data["choices"][0]["message"]["content"].strip()

    # Try to parse as JSON
    try:
        # Handle cases where AI wraps JSON in markdown code blocks
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)

        # Ensure result has required fields
        if not isinstance(result, dict) or "reply" not in result:
            raise ValueError("Invalid response format")

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to parse AI response: {e}")
        print(f"Raw response: {raw_text[:200]}")

        # Try to extract reply field from partial JSON using regex
        try:
            import re
            reply_match = re.search(r'"reply":\s*"([^"]*(?:\\.[^"]*)*)"', raw_text)
            if reply_match:
                extracted_reply = reply_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            else:
                extracted_reply = "দুঃখিত, আমি এখন একটু সমস্যায় পড়েছি। একটু পরে আবার চেষ্টা করুন।"
        except Exception as extract_error:
            print(f"Extraction failed: {extract_error}")
            extracted_reply = "দুঃখিত, আমি এখন একটু সমস্যায় পড়েছি। একটু পরে আবার চেষ্টা করুন।"

        # Use fallback response
        result = {
            "reply": extracted_reply,
            "intent": "general",
            "order_data": None,
            "needs_human": True,
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
    new_order = None
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
        db.flush()  # Get the order ID before commit

        # Decrement stock for matching product
        for p in products:
            if p.name.lower() in order_data["product"].lower() or order_data["product"].lower() in p.name.lower():
                if p.stock is not None and p.stock > 0:
                    p.stock -= 1
                    if p.stock == 0:
                        p.is_available = False
                break

        # Update customer info
        customer.name = order_data["customer_name"]
        customer.phone = order_data["phone"]
        customer.address = order_data["address"]
        customer.total_orders = (customer.total_orders or 0) + 1

        new_order = order

    db.commit()

    # Attach order info to result if created
    if new_order:
        result["new_order"] = {
            "id": new_order.id[:8],  # Short ID for customer
            "full_id": new_order.id,
            "product": order_data["product"],
            "customer_name": order_data["customer_name"],
            "phone": order_data["phone"],
            "address": order_data["address"],
            "payment_method": order_data.get("payment_method", "COD"),
        }

    return result
