from typing import List, Dict
from fastapi import HTTPException
from . import scraper
from .schemas import OptimizeRequest, BundleItem, OptimizeResponse


def optimize_ammo_bundle(request: OptimizeRequest) -> OptimizeResponse:
    # Fetch & filter per item
    listings_by_item: List[List[Dict]] = []
    for item in request.items:
        lst = scraper.scrape_ammoseek(
            caliber=item.caliber,
            bullet_weight=item.bullet_weight,
            search_terms=item.search_terms,
            case_material=item.case_material,
            condition=item.condition,
            min_shipping_rating=request.min_shipping_rating,
            min_qty=item.min_qty,
            max_qty=item.max_qty,
            manufacturers=item.manufacturers,
        )
        if not lst:
            raise HTTPException(404, f"No listings for {item.caliber} matching filters")
        listings_by_item.append(lst)

    all_retailers = {l["retailer"] for listings in listings_by_item for l in listings}
    free_by_item = [[l for l in listings if l.get("shipping_rating") == 10]
                    for listings in listings_by_item]

    best_cost = float('inf')
    best_bundle: List[BundleItem] = []

    for retailer in all_retailers:
        # single-shop bundle
        bundle: List[BundleItem] = []
        ok = True
        for idx, item in enumerate(request.items):
            candidates = [l for l in listings_by_item[idx]
                          if l.get("retailer")==retailer
                          and ((l.get("shipping_rating") or 0)>=request.min_shipping_rating or l.get("shipping_rating")==10)]
            if not candidates:
                ok=False; break
            best_l = min(candidates, key=lambda x: x.get("price_per_round", float('inf')))
            qty = item.min_qty
            bundle.append(BundleItem(
                caliber=item.caliber,
                bullet_weight=item.bullet_weight,
                manufacturer=best_l.get("mfg"),
                retailer=retailer,
                product_url=best_l.get("product_url"),
                unit_price=best_l.get("price_per_round"),
                quantity=qty,
                total_price=round(best_l.get("price_per_round",0)*qty,2),
                shipping_rating=best_l.get("shipping_rating"),
            ))
        if ok:
            cost = sum(b.total_price for b in bundle)
            if cost<best_cost:
                best_cost, best_bundle = cost, bundle

        # hybrid bundle
        bundle=[]; ok=True
        for idx, item in enumerate(request.items):
            prim = [l for l in listings_by_item[idx]
                    if l.get("retailer")==retailer
                    and (l.get("shipping_rating") or 0)>=request.min_shipping_rating]
            if prim:
                sel=prim
            else:
                sel=free_by_item[idx]
                if not sel: ok=False; break
            best_l = min(sel, key=lambda x: x.get("price_per_round", float('inf')))
            qty=item.min_qty
            bundle.append(BundleItem(
                caliber=item.caliber,
                bullet_weight=item.bullet_weight,
                manufacturer=best_l.get("mfg"),
                retailer=best_l.get("retailer"),
                product_url=best_l.get("product_url"),
                unit_price=best_l.get("price_per_round"),
                quantity=qty,
                total_price=round(best_l.get("price_per_round",0)*qty,2),
                shipping_rating=best_l.get("shipping_rating"),
            ))
        if ok:
            cost=sum(b.total_price for b in bundle)
            if cost<best_cost:
                best_cost, best_bundle = cost, bundle

    if not best_bundle:
        raise HTTPException(404, "Unable to build valid bundle.")

    return OptimizeResponse(total_cost=round(best_cost,2), bundles=best_bundle)
