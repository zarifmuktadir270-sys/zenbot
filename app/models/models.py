from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.models.database import Base


def generate_uuid():
    return str(uuid.uuid4())


# === Plan feature gating ===
PLAN_FEATURES = {
    "trial": {
        "price_bdt": 0,
        "features": ["welcome_message", "quick_replies", "order_tracking", "auto_comment_reply"],
    },
    "starter": {
        "price_bdt": 2999,
        "features": ["welcome_message", "quick_replies", "order_tracking", "auto_comment_reply",
                      "auto_followup", "product_categories", "customer_tags", "export_csv"],
    },
    "growth": {
        "price_bdt": 5999,
        "features": ["welcome_message", "quick_replies", "order_tracking", "auto_comment_reply",
                      "auto_followup", "product_categories", "customer_tags", "export_csv",
                      "broadcast", "analytics", "dashboard_reply", "sound_notifications", "coupons"],
    },
    "professional": {
        "price_bdt": 9999,
        "features": ["welcome_message", "quick_replies", "order_tracking", "auto_comment_reply",
                      "auto_followup", "product_categories", "customer_tags", "export_csv",
                      "broadcast", "analytics", "dashboard_reply", "sound_notifications", "coupons",
                      "invoices", "whatsapp"],
    },
}


def has_feature(plan: str, feature: str) -> bool:
    return feature in PLAN_FEATURES.get(plan, PLAN_FEATURES["trial"])["features"]


class Seller(Base):
    __tablename__ = "sellers"

    id = Column(String, primary_key=True, default=generate_uuid)
    fb_page_id = Column(String, unique=True, nullable=False)
    fb_page_name = Column(String)
    fb_page_access_token = Column(String, nullable=False)
    admin_fb_user_id = Column(String)

    delivery_info = Column(Text, default="Dhaka: 60 BDT, Outside Dhaka: 120 BDT")
    payment_methods = Column(Text, default="bKash, Nagad, COD")
    delivery_time = Column(Text, default="Dhaka: 1-2 days, Outside Dhaka: 3-5 days")
    return_policy = Column(Text, default="7 days return policy")

    bot_name = Column(String, default="AI Assistant")
    bot_personality = Column(String, default="friendly")
    custom_instructions = Column(Text, default="")
    learned_knowledge = Column(Text, default="")
    welcome_message = Column(Text, default="")  # Auto-sent to new customers

    plan = Column(String, default="trial")
    plan_expires_at = Column(DateTime)

    is_active = Column(Boolean, default=True)
    bot_paused = Column(Boolean, default=False)
    dashboard_pin = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="seller")
    customers = relationship("Customer", back_populates="seller")
    conversations = relationship("Conversation", back_populates="seller")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)

    fb_post_id = Column(String)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    price_text = Column(String)
    category = Column(String, default="")
    image_url = Column(String)
    stock = Column(Integer, default=-1)
    is_available = Column(Boolean, default=True)
    raw_post_text = Column(Text)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="products")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)

    fb_user_id = Column(String, nullable=False)
    name = Column(String)
    phone = Column(String)
    address = Column(Text)
    total_orders = Column(Integer, default=0)
    notes = Column(Text)
    tags = Column(String, default="")  # Comma-separated: "vip,frequent,new"
    is_welcomed = Column(Boolean, default=False)  # Track if welcome message sent
    last_order_followed_up = Column(String)  # Last order ID that got follow-up

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="customers")
    conversations = relationship("Conversation", back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)

    sender = Column(String, nullable=False)  # "customer", "agent", or "seller"
    message = Column(Text, nullable=False)
    intent = Column(String)
    metadata_ = Column("metadata", JSON)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="conversations")
    customer = relationship("Customer", back_populates="conversations")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)

    items = Column(JSON)
    total_amount = Column(Float, default=0)
    status = Column(String, default="pending")
    customer_name = Column(String)
    customer_phone = Column(String)
    customer_address = Column(Text)
    payment_method = Column(String)
    coupon_code = Column(String)  # Applied coupon
    discount_amount = Column(Float, default=0)
    notes = Column(Text)
    followed_up = Column(Boolean, default=False)  # 24hr follow-up sent?

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Media(Base):
    __tablename__ = "media"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)
    media_type = Column(String, default="image")
    tags = Column(String, default="")
    file_data = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PlanRequest(Base):
    __tablename__ = "plan_requests"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    requested_plan = Column(String, nullable=False)
    payment_method = Column(String, default="bkash")  # bkash, nagad, bank
    transaction_id = Column(String, nullable=False)
    amount_bdt = Column(Float, default=0)
    status = Column(String, default="pending")  # pending, approved, rejected
    admin_note = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    code = Column(String, nullable=False)  # e.g. "EID20"
    discount_type = Column(String, default="percentage")  # "percentage" or "fixed"
    discount_value = Column(Float, nullable=False)  # 20 = 20% or 200 = 200 BDT
    min_order = Column(Float, default=0)  # Minimum order amount
    max_uses = Column(Integer, default=-1)  # -1 = unlimited
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
