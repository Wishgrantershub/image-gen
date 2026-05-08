from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderBase(BaseModel):
    story_id: int
    amount: float
    currency: str = "USD"

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    user_id: int
    payment_status: str
    shipping_status: str
    shipping_address: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentInitResponse(BaseModel):
    order_id: str
    razorpay_order_id: str
    amount: float
    currency: str