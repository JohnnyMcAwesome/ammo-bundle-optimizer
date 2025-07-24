from typing import List, Optional
from pydantic import BaseModel


class AmmoItemRequest(BaseModel):
    caliber: str
    min_qty: int
    max_qty: int
    bullet_weight: Optional[int] = None
    search_terms: Optional[List[str]] = None
    case_material: Optional[str] = None
    condition: Optional[str] = None


class OptimizeRequest(BaseModel):
    items: List[AmmoItemRequest]
    min_shipping_rating: Optional[int] = None
