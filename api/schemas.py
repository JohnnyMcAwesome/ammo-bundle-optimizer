from typing import List, Optional
from pydantic import BaseModel, Field


class AmmoItemRequest(BaseModel):
    """
    Single ammo item with desired characteristics and quantities.
    """
    caliber: str
    min_qty: int
    max_qty: int
    bullet_weight: Optional[int] = None
    search_terms: Optional[List[str]] = None
    case_material: Optional[str] = None
    condition: Optional[str] = None


class OptimizeRequest(BaseModel):
    """
    Overall optimization request containing multiple AmmoItemRequests
    and a minimum shipping rating filter.
    """
    items: List[AmmoItemRequest]
    min_shipping_rating: Optional[int] = Field(default=0, ge=0, le=10)


class BundleItem(BaseModel):
    """
    Resulting best bundle choice for a single AmmoItemRequest.
    """
    retailer: str
    product_url: Optional[str] = None
    unit_price: float
    quantity: int
    total_price: float
    shipping_rating: Optional[int] = None


class OptimizeResponse(BaseModel):
    """
    Aggregated response containing total cost and individual bundles.
    """
    total_cost: float
    bundles: List[BundleItem]
