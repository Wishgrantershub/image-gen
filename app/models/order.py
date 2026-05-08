from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class ShippingStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    shipping_status = Column(SQLEnum(ShippingStatus), default=ShippingStatus.NOT_STARTED)
    shipping_address = Column(String, nullable=True)
    tracking_number = Column(String, nullable=True)
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    story = relationship("Story", back_populates="order")