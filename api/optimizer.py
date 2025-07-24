from typing import List
from fastapi import HTTPException
from . import scraper
from .schemas import OptimizeRequest, BundleItem, OptimizeResponse

def optimize_ammo_bundle(request: OptimizeRequest) -> OptimizeResponse:
    """
    Given an OptimizeRequest, fetch listings via the scraper (which now
    knows whether to use 'handgun' or 'rifle'), apply the minimum shipping
    rating and quantity filters, then choose the cheapest single‑vendor
    bundle for each item and total it up.
    """
    bundles: List[BundleItem] = []
    for item in request.items:
        raw_listings = scraper.scrape_ammoseek(
            caliber=item.caliber,
            bullet_weight=item.bullet_weight,
            search_terms=item.search_terms,
            case_material=item.case_material,
            condition=item.condition,
            min_shipping_rating=request.min_shipping_rating,
            min_qty=item.min_qty,
            max_qty=item.max_qty,
        )
        if not raw_listings:
            raise HTTPException(
                status_code=404,
                detail=f"No listings for {item.caliber} matching filters"
            )

        # Pick the listing with the lowest price_per_round
        best = min(
            raw_listings,
            key=lambda l: l.get("price_per_round", float('inf'))
        )

        # Use the minimum quantity requested
        qty = item.min_qty

        bundles.append(
            BundleItem(
                retailer=best["retailer"],
                product_url=best["product_url"],
                unit_price=best["price_per_round"],
                quantity=qty,
                total_price=round(best["price_per_round"] * qty, 2),
                shipping_rating=best["shipping_rating"],
            )
        )

    total_cost = sum(b.total_price for b in bundles)
    return OptimizeResponse(
        total_cost=round(total_cost, 2),
        bundles=bundles,
    )
