"""
Facebook Messenger API utility — Sends messages back to customers.
"""

import hmac
import hashlib
import httpx

from app.config import settings

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def send_message(recipient_id: str, message_text: str, page_access_token: str):
    """Send a text message to a customer via Messenger."""
    url = f"{GRAPH_API_BASE}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, json=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.status_code} {response.text}")
        return response.json()


async def send_product_cards(recipient_id: str, products: list, page_access_token: str):
    """Send product cards with images as a carousel in Messenger."""
    if not products:
        return

    elements = []
    for p in products[:10]:  # Max 10 cards in a carousel
        element = {
            "title": p.get("name", "Product")[:80],
            "subtitle": p.get("subtitle", "")[:80],
        }
        if p.get("image_url"):
            element["image_url"] = p["image_url"]
        if p.get("price"):
            element["subtitle"] = f"Price: {p['price']}"
        elements.append(element)

    url = f"{GRAPH_API_BASE}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements,
                }
            }
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, json=payload)
        if response.status_code != 200:
            print(f"Failed to send product cards: {response.status_code} {response.text}")
        return response.json()


async def send_private_reply(comment_id: str, message_text: str, page_access_token: str):
    """Send a private reply (DM) to someone who commented on a post."""
    url = f"{GRAPH_API_BASE}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, json=payload)
        if response.status_code != 200:
            print(f"Private reply failed: {response.status_code} {response.text}")
        return response.json()


async def send_typing_indicator(recipient_id: str, page_access_token: str, action: str = "typing_on"):
    """Show typing indicator while AI processes the message."""
    url = f"{GRAPH_API_BASE}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action,
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, params=params, json=payload)


async def send_quick_replies(recipient_id: str, message_text: str, replies: list, page_access_token: str):
    """Send a message with quick reply buttons."""
    url = f"{GRAPH_API_BASE}/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {
            "text": message_text,
            "quick_replies": [
                {"content_type": "text", "title": r, "payload": r}
                for r in replies[:13]  # Max 13 quick replies
            ],
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, json=payload)
        return response.json()


async def get_user_profile(user_id: str, page_access_token: str) -> dict:
    """Get the customer's Facebook name and profile picture."""
    url = f"{GRAPH_API_BASE}/{user_id}"
    params = {
        "access_token": page_access_token,
        "fields": "first_name,last_name,profile_pic",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return {}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify that the webhook request actually came from Facebook."""
    if not settings.fb_app_secret:
        return True  # Skip in development

    expected = hmac.new(
        settings.fb_app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)
