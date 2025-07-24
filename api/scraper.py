import re
import httpx
from urllib.parse import urlencode
from typing import List, Optional, Dict

BASE_URL = "https://ammoseek.com"
SEARCH_ENDPOINT = "/"

# Map user-friendly caliber inputs to AmmoSeek URL slugs
CALIBER_SLUGS = {
    "9mm":       "9mm-luger",
    "5.56":      "5.56-nato",
    "45acp":     "45-acp",
    "38special": "38-special",
    # extend as needed
}

# Map slug to numeric caliber ID as used by AmmoSeek
CALIBER_IDS = {
    "9mm-luger": "82",
    "5.56-nato": "49",
    # add other calibers here
}

# Which slugs correspond to rifle calibers (to set gun parameter)
RIFLE_SLUGS = {"5.56-nato"}

# DataTables columns order expected by AmmoSeek
COLUMNS = [
    "retailer", "descr", "mfg", "caliber", "grains", "when",
    "purchaselimit", "casing", "condition", "price", "count", "cp",
    "shipping_rating", "share", "dr"
]


def build_search_payload(
    slug: str,
    caliber_id: str,
    bullet_weight: Optional[int],
    search_terms: Optional[List[str]],
    case_material: Optional[str],
    condition: Optional[str],
    min_shipping_rating: Optional[int],
    min_qty: Optional[int],
    max_qty: Optional[int]
) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    # DataTables column metadata
    for i, col in enumerate(COLUMNS):
        payload[f"columns[{i}][data]"] = col
        payload[f"columns[{i}][name]"] = ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "false"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    # Paging and draw
    payload.update({
        "draw": "1",
        "start": "0",
        "length": str(max_qty or 100),
        "search[value]": "",
        "search[regex]": "false"
    })

    # Filters
    payload["search_ammo"] = "1"
    if min_shipping_rating is not None:
        if min_shipping_rating >= 8:
            payload["sh"] = "low"
        elif min_shipping_rating >= 6:
            payload["sh"] = "average"
        elif min_shipping_rating >= 4:
            payload["sh"] = "high"
    if case_material:
        payload["ca"] = case_material.lower()
    payload["sort"] = ""
    # Rifle vs handgun
    payload["gun"] = "rifle" if slug in RIFLE_SLUGS else "handgun"
    payload["cal"] = caliber_id
    if search_terms:
        payload["ikw"] = " ".join(search_terms)
    if bullet_weight is not None:
        payload["grains"] = str(bullet_weight)
    if min_qty is not None and max_qty is not None:
        payload["nr"] = f"{min_qty}-{max_qty}"
    payload["ekw"] = ""
    if condition:
        payload["co"] = condition.lower()
    payload["seo_name"] = slug

    return payload


def parse_listings(json_data: List[dict]) -> List[dict]:
    listings = []
    for row in json_data:
        retailer = row.get("retailer")
        descr = row.get("descr", "")
        # strip HTML from description
        title = re.sub(r'<[^>]+>', '', descr).strip()

        # cost-per-round (cp) comes in cents markup
        cp_text = row.get("cp", "").replace('&#162;', '¢')
        cp_num = None
        match = re.search(r"([0-9]+\.?[0-9]*)", cp_text)
        if match:
            try:
                cp_num = float(match.group(1)) / 100.0
            except ValueError:
                cp_num = None

        # fallback: total price / count
        if cp_num is None:
            price_txt = row.get("price", "")
            price_num = re.sub(r'[^0-9\.]', '', price_txt)
            try:
                total_price = float(price_num)
                count = int(row.get("count", 1))
                cp_num = total_price / count
            except Exception:
                cp_num = None

        # shipping rating: "free" -> 10, else numeric parse
        ship_raw = row.get("shipping_rating", "").lower()
        if ship_raw == "free":
            ship_rating = 10
        else:
            m = re.search(r"(\d+)", ship_raw)
            ship_rating = int(m.group(1)) if m else None

        # product URL from DT_RowData.gourl
        dt = row.get("DT_RowData", {})
        gourl = dt.get("gourl")
        product_url = f"{BASE_URL}{gourl}" if gourl else None

        listings.append({
            "retailer": retailer,
            "title": title,
            "product_url": product_url,
            "price_per_round": cp_num,
            "shipping_rating": ship_rating
        })
    return listings


def scrape_ammoseek(
    caliber: str,
    bullet_weight: Optional[int] = None,
    search_terms: Optional[List[str]] = None,
    case_material: Optional[str] = None,
    condition: Optional[str] = None,
    min_shipping_rating: Optional[int] = None,
    min_qty: Optional[int] = None,
    max_qty: Optional[int] = None
) -> List[dict]:
    """
    Perform a JSON POST to AmmoSeek's DataTables endpoint to fetch listings.
    """
    # Determine slug and caliber ID
    key = caliber.lower().replace(" ", "")
    slug = CALIBER_SLUGS.get(key, key)
    caliber_id = CALIBER_IDS.get(slug)
    if not caliber_id:
        raise ValueError(f"Unknown caliber slug '{slug}' for JSON API")

    # Build form data
    payload = build_search_payload(
        slug,
        caliber_id,
        bullet_weight,
        search_terms,
        case_material,
        condition,
        min_shipping_rating,
        min_qty,
        max_qty
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        # Use correct referer for rifle vs handgun
        "Referer": (
            f"{BASE_URL}/ammo/{slug}/" if bullet_weight is None else \
            f"{BASE_URL}/ammo/{slug}/-handgun-{bullet_weight}grains"
        )
    }

    with httpx.Client() as client:
        # fetch page first to get any cookies if needed
        client.get(f"{BASE_URL}/ammo/{slug}/")
        resp = client.post(
            BASE_URL + SEARCH_ENDPOINT,
            data=payload,
            headers=headers,
        )
        resp.raise_for_status()
        result = resp.json()

    return parse_listings(result.get("data", []))
