from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint
from typing import List, Optional

router = APIRouter()

class AmmoRequestItem(BaseModel):
    caliber: str = Field(..., description="Caliber, e.g. '9mm'")
    min_qty: conint(ge=1) = Field(..., description="Minimum quantity to buy")
    max_qty: conint(ge=1) = Field(..., description="Maximum quantity to buy")
    bullet_weight: Optional[int] = Field(None, description="Bullet weight in grains")
    search_terms: Optional[List[str]] = Field(None, description="Optional search keywords")
    case_material: Optional[str] = Field(None, description="Case material filter, e.g. 'Brass'")
    condition: Optional[str] = Field(None, description="Condition filter, e.g. 'New', 'Reman'")

class OptimizeRequest(BaseModel):
    items: List[AmmoRequestItem]
    min_shipping_rating: Optional[conint(ge=1, le=10)] = Field(1, description="Minimum shipping rating (1-10)")

@router.post("/")
async def optimize_ammo(request: OptimizeRequest):
    # Stub: here you'd call your scraper & optimizer logic
    # For now, just echo back the request
    return {"received": request.dict()}

