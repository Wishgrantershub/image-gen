from typing import List, Optional
from pydantic import BaseModel


class ComicStyleOut(BaseModel):
    id: str
    name: str
    tagline: str
    description: str
    emoji: str
    accent_color: str
    preview_palette: List[str]
    default_panel_count: int
    sample_premises: List[str]


class ComicTierOut(BaseModel):
    id: str
    name: str
    panel_count: int
    panel_layout: str
    price_inr: int
    tagline: str


class ComicStylesTiersResponse(BaseModel):
    styles: List[ComicStyleOut]
    tiers: List[ComicTierOut]


class ComicCreateRequest(BaseModel):
    child_id: int
    style_id: str
    tier_id: str
    premise: str
    title: Optional[str] = None
    payment_verified: bool = False
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None


class ComicPanelOut(BaseModel):
    page_number: int
    caption: str
    speech: str
    bubble_kind: str
    image_url: str
    image_path: Optional[str] = None


class ComicResponse(BaseModel):
    id: int
    share_token: str
    title: str
    style_id: str
    tier_id: str
    panel_count: int
    panel_layout: str
    status: str
    progress_step: Optional[str] = None
    progress_message: Optional[str] = None
    progress_pct: int
    error_message: Optional[str] = None
    cover_url: Optional[str] = None
    pdf_url: Optional[str] = None
    share_url: Optional[str] = None
    panels: List[ComicPanelOut] = []
    is_paid: bool = False
    payment_required: bool = False
    amount_inr: Optional[float] = None


class ComicStatusResponse(BaseModel):
    id: int
    status: str
    progress_step: Optional[str] = None
    progress_message: Optional[str] = None
    progress_pct: int
    error_message: Optional[str] = None
    pdf_url: Optional[str] = None
    cover_url: Optional[str] = None
    panel_count: int
    completed_panels: int = 0
    ready_panel_numbers: List[int] = []


class SampleComicRequest(BaseModel):
    name: str
    style_id: str
    tier_id: str
    premise: Optional[str] = None
    photo: Optional[str] = None


class PaymentOrderRequest(BaseModel):
    tier_id: str
    style_id: Optional[str] = None
    child_id: Optional[int] = None
    amount_inr: Optional[int] = None
    story_id: Optional[int] = None


class PaymentOrderResponse(BaseModel):
    order_id: str
    amount_inr: int
    currency: str
    tier_id: str
    key_id: str
    status: str


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    story_id: Optional[int] = None
    session_token: Optional[str] = None


class PaymentVerifyResponse(BaseModel):
    verified: bool
    message: str
    story_id: Optional[int] = None
    is_paid: Optional[bool] = None
