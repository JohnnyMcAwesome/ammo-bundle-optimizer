from collections import defaultdict
from fastapi import HTTPException
from api.schemas import OptimizeRequest, AmmoItemRequest
from api.scraper import scrape_ammoseek
from typing import List


def optimize_ammo_bundle(request: OptimizeRequest) -> dict:
    """
    For each AmmoItemRequest in the incoming request, scrape a full list of
    listings for its caliber, then apply item-level filters in Python (bullet weight,
    search terms, case material, condition, shipping rating), and find the cheapest
    single-retailer bundle that fulfills all items at the requested quantities.
    """
    # 1) Scrape full lists per caliber
    listings_by_item: List[tuple[AmmoItemRequest, List[dict]]] = []
    for item in request.items:
        raw = scrape_ammoseek(item.caliber)
        # Python-level filtering
        filtered = []
        for l in raw:
            # Weight filter
            if item.bullet_weight is not None and l.get("bullet_weight") != item.bullet_weight:
                continue
            # Search terms filter
            if item.search_terms:
                title = l.get("title") or ""
                if not all(term.lower() in title.lower() for term in item.search_terms):
                    continue
            # Case material filter
            if item.case_material and l.get("case_material") != item.case_material:
                continue
            # Condition filter
            if item.condition and l.get("condition") != item.condition:
                continue
            # Shipping rating filter (None => 0)
            ship = l.get("shipping_rating") or 0
            if request.min_shipping_rating and ship < request.min_shipping_rating and ship != 10:
                continue
            filtered.append(l)
        if not filtered:
            raise HTTPException(
                status_code=404,
                detail=f"No listings for {item.caliber} matching filters"
            )
        listings_by_item.append((item, filtered))

    # 2) Map each retailer -> {caliber: best_listing_for_item}
    retailer_map: dict[str, dict[str, dict]] = defaultdict(dict)
    for item, listings in listings_by_item:
        for l in listings:
            retailer = l["retailer"]
            current = retailer_map[retailer].get(item.caliber)
            if current is None or (l.get("price_per_round") or 0) < (current.get("price_per_round") or 0):
                retailer_map[retailer][item.caliber] = l

    # 3) Evaluate total cost per retailer
    best = {"retailer": None, "total_cost": float("inf"), "breakdown": []}
    needed = [item.caliber for item in request.items]

    for retailer, calib_map in retailer_map.items():
        # must cover all requested calibers
        if set(calib_map.keys()) != set(needed):
            continue
        total = 0.0
        breakdown = []
        for item, listings in listings_by_item:
            # use listing chosen above
            l = calib_map[item.caliber]
            qty = item.min_qty
            cost = (l.get("price_per_round") or 0) * qty
            total += cost
            breakdown.append({
                "caliber": item.caliber,
                "qty": qty,
                "unit_price": l.get("price_per_round"),
                "item_cost": cost,
                "retailer": retailer,
                "product_url": l.get("product_url"),
                "shipping_rating": l.get("shipping_rating")
            })
        if total < best["total_cost"]:
            best = {"retailer": retailer, "total_cost": total, "breakdown": breakdown}

    if best["retailer"] is None:
        raise HTTPException(status_code=404, detail="No single retailer can fulfill all items.")

    return best
