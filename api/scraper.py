import re
import httpx
from typing import List, Optional, Dict

BASE_URL = "https://ammoseek.com"
SEARCH_ENDPOINT = "/"

CALIBER_SLUGS = {
    "9mm":       "9mm-luger",
    "5.56":      "5.56-nato",
    "45acp":     "45-acp",
    "38special": "38-special",
}

CALIBER_IDS = {
    "9mm-luger":  "82",
    "5.56-nato":  "49",
}

RIFLE_SLUGS = {"5.56-nato"}

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
    # DataTables columns config
    for i, col in enumerate(COLUMNS):
        payload[f"columns[{i}][data]"] = col
        payload[f"columns[{i}][name]"] = ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "false"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    # Paging & draw
    payload.update({
        "draw": "1",
        "start": "0",
        "length": str(max_qty or 100),
        "search[value]": "",
        "search[regex]": "false",
    })

    # Core filters
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
        title = re.sub(r"<[^>]+>", "", descr).strip()
        mfg = row.get("mfg")  # the JSON field for brand

        # price-per-round parsing
        cp_txt = row.get("cp", "").strip()
        cp: Optional[float] = None
        if "¢" in cp_txt:
            m = re.search(r"([0-9]+\.?[0-9]*)", cp_txt)
            if m:
                cp = float(m.group(1)) / 100.0
        elif "$" in cp_txt:
            m = re.search(r"([0-9]+\.?[0-9]*)", cp_txt)
            if m:
                cp = float(m.group(1))
        if cp is None:
            ptxt = row.get("price", "")
            pnum = re.sub(r"[^0-9\.]", "", ptxt)
            try:
                tot = float(pnum)
                cnt = int(row.get("count", 1))
                cp = tot / cnt
            except:
                cp = None

        # shipping rating
        sr = row.get("shipping_rating", "").lower()
        if sr == "free":
            ship = 10
        else:
            m2 = re.search(r"(\d+)", sr)
            ship = int(m2.group(1)) if m2 else None

        # product URL
        dt = row.get("DT_RowData", {})
        gourl = dt.get("gourl")
        url = f"{BASE_URL}{gourl}" if gourl else None

        listings.append({
            "retailer": retailer,
            "mfg": mfg,
            "title": title,
            "product_url": url,
            "price_per_round": cp,
            "shipping_rating": ship,
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
    max_qty: Optional[int] = None,
    manufacturers: Optional[List[str]] = None
) -> List[dict]:
    key = caliber.lower().replace(" ", "")
    slug = CALIBER_SLUGS.get(key, key)
    caliber_id = CALIBER_IDS.get(slug)
    if not caliber_id:
        raise ValueError(f"Unknown caliber slug '{slug}' for JSON API")

    # Fetch raw listings once
    raw = _fetch_listings(
        slug, caliber_id,
        bullet_weight, search_terms,
        case_material, condition,
        min_shipping_rating,
        min_qty, max_qty
    )

    # Apply Python-side, case-insensitive manufacturer filter
    if manufacturers:
        allowed = {m.lower() for m in manufacturers}
        raw = [l for l in raw if (l.get("mfg") or "").lower() in allowed]

    # Deduplicate by URL
    seen = set()
    unique = []
    for l in raw:
        url = l.get("product_url")
        if url and url not in seen:
            seen.add(url)
            unique.append(l)

    return unique


def _fetch_listings(
    slug: str,
    caliber_id: str,
    bullet_weight: Optional[int],
    search_terms: Optional[List[str]],
    case_material: Optional[str],
    condition: Optional[str],
    min_shipping_rating: Optional[int],
    min_qty: Optional[int],
    max_qty: Optional[int]
) -> List[dict]:
    payload = build_search_payload(
        slug, caliber_id,
        bullet_weight, search_terms,
        case_material, condition,
        min_shipping_rating,
        min_qty, max_qty
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/ammo/{slug}/",
    }
    with httpx.Client() as client:
        client.get(f"{BASE_URL}/ammo/{slug}/")
        resp = client.post(
            BASE_URL + SEARCH_ENDPOINT,
            data=payload,
            headers=headers
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    return parse_listings(data)
