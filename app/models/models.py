from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.models.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Seller(Base):
    """A seller/shop that uses our service."""
    __tablename__ = "sellers"

    id = Column(String, primary_key=True, default=generate_uuid)
    fb_page_id = Column(String, unique=True, nullable=False)
    fb_page_name = Column(String)
    fb_page_access_token = Column(String, nullable=False)
    admin_fb_user_id = Column(String)  # Page admin's FB user ID for notifications

    # Seller setup info (the 4 questions)
    delivery_info = Column(Text, default="Dhaka: 60 BDT, Outside Dhaka: 120 BDT")
    payment_methods = Column(Text, default="bKash, Nagad, COD")
    delivery_time = Column(Text, default="Dhaka: 1-2 days, Outside Dhaka: 3-5 days")
    return_policy = Column(Text, default="7 days return policy")

    # Custom AI config
    bot_name = Column(String, default="AI Assistant")
    bot_personality = Column(String, default="friendly")  # friendly, professional, casual, funny
    custom_instructions = Column(Text, default="")  # Seller's custom rules for the bot
    learned_knowledge = Column(Text, default="")  # Auto-learned from owner corrections

    # Subscription
    plan = Column(String, default="trial")  # trial, starter, growth, professional
    plan_expires_at = Column(DateTime)

    is_active = Column(Boolean, default=True)
    bot_paused = Column(Boolean, default=False)  # Seller can pause/resume bot
    dashboard_pin = Column(String)  # Hashed PIN for dashboard security
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="seller")
    customers = relationship("Customer", back_populates="seller")
    conversations = relationship("Conversation", back_populates="seller")


class Product(Base):
    """Products scraped from seller's Facebook page."""
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)

    fb_post_id = Column(String)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    price_text = Column(String)  # Original text like "1200 BDT" or "1200/-"
    category = Column(String)
    image_url = Column(String)
    stock = Column(Integer, default=-1)  # -1 = unlimited, 0 = out of stock, >0 = exact count
    is_available = Column(Boolean, default=True)
    raw_post_text = Column(Text)  # Full original post text for AI context

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="products")


class Customer(Base):
    """Customers who message the seller's page."""
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)

    fb_user_id = Column(String, nullable=False)
    name = Column(String)
    phone = Column(String)
    address = Column(Text)
    total_orders = Column(Integer, default=0)
    notes = Column(Text)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="customers")
    conversations = relationship("Conversation", back_populates="customer")


class Conversation(Base):
    """Message history between customer and AI agent."""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)

    sender = Column(String, nullable=False)  # "customer" or "agent"
    message = Column(Text, nullable=False)
    intent = Column(String)  # inquiry, order, complaint, tracking, general
    metadata_ = Column("metadata", JSON)  # Extra data (order details, etc.)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="conversations")
    customer = relationship("Customer", back_populates="conversations")


class Order(Base):
    """Orders placed through the chatbot."""
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)

    items = Column(JSON)  # [{"product_name": "...", "quantity": 1, "price": 1200}]
    total_amount = Column(Float, default=0)
    status = Column(String, default="pending")  # pending, confirmed, shipped, delivered, cancelled
    customer_name = Column(String)
    customer_phone = Column(String)
    customer_address = Column(Text)
    payment_method = Column(String)
    notes = Column(Text)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Media(Base):
    """Media files uploaded by sellers for the bot to send."""
    __tablename__ = "media"

    id = Column(String, primary_key=True, default=generate_uuid)
    seller_id = Column(String, ForeignKey("sellers.id"), nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)
    media_type = Column(String, default="image")  # image, video
    tags = Column(String, default="")  # Comma-separated tags for AI to match
    file_data = Column(Text)  # Base64-encoded file data for uploaded files
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
