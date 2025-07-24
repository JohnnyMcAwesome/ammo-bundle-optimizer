import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlencode
from typing import List, Optional, Dict

BASE_URL = "https://ammoseek.com/ammo/"

# Map user-friendly caliber inputs to AmmoSeek URL slugs
CALIBER_SLUGS = {
    "9mm":       "9mm-luger",
    "5.56":      "5.56-nato",
    "45acp":     "45-acp",
    "38special": "38-special",
    # extend as needed
}

def build_search_url(
    caliber: str,
    bullet_weight: Optional[int] = None,
    search_terms: Optional[List[str]] = None,
    case_material: Optional[str] = None,
    condition: Optional[str] = None,
    min_shipping_rating: Optional[int] = None,
    min_qty: Optional[int] = None,
    max_qty: Optional[int] = None
) -> str:
    key = caliber.lower().replace(" ", "")
    slug = CALIBER_SLUGS.get(key, caliber)
    path = f"{BASE_URL}{slug}"
    if bullet_weight is not None:
        path += f"/-handgun-{bullet_weight}grains"

    params: Dict[str, str] = {}
    if case_material:
        params["ca"] = case_material.lower()
    if condition:
        params["co"] = condition.lower()
    if search_terms:
        params["ikw"] = " ".join(search_terms)
    if min_qty is not None and max_qty is not None:
        params["nr"] = f"{min_qty}-{max_qty}"
    if min_shipping_rating is not None:
        if min_shipping_rating >= 8:
            params["sh"] = "low"
        elif min_shipping_rating >= 6:
            params["sh"] = "average"
        elif min_shipping_rating >= 4:
            params["sh"] = "high"

    query = urlencode(params)
    return f"{path}?{query}" if query else path


def scrape_ammoseek(
    caliber: str,
    bullet_weight: Optional[int] = None,
    search_terms: Optional[List[str]] = None,
    case_material: Optional[str] = None,
    condition: Optional[str] = None,
    min_shipping_rating: Optional[int] = None,
    min_qty: Optional[int] = None,
    max_qty: Optional[int] = None
) -> List[Dict]:
    url = build_search_url(
        caliber,
        bullet_weight,
        search_terms,
        case_material,
        condition,
        min_shipping_rating,
        min_qty,
        max_qty,
    )
    print(f"Scraping: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        )
        try:
            page.goto(url, timeout=60000, wait_until="networkidle")
            # Wait for DataTables rows
            page.wait_for_selector("div#ammo_wrapper tbody tr", timeout=30000)
            # Extract structured data via DOM evaluation
            data = page.evaluate("() => { \
                const rows = document.querySelectorAll('div#ammo_wrapper tbody tr'); \
                return Array.from(rows).map(row => { \
                    const cells = row.querySelectorAll('td'); \
                    const retailer = cells[0]?.textContent.trim() || null; \
                    const link = cells[1]?.querySelector('a'); \
                    const title = link?.textContent.trim() || null; \
                    const href = link?.getAttribute('href') || null; \
                    const product_url = href ? `https://ammoseek.com${href}` : null; \
                    const priceText = cells[2]?.textContent.trim() || ''; \
                    const price = priceText.startsWith('$') ? parseFloat(priceText.replace('$','')) : null; \
                    const shipEl = cells[3]?.querySelector('.displayScore'); \
                    const shipping_rating = shipEl ? parseInt(shipEl.textContent.trim()) : null; \
                    return { retailer, title, product_url, price_per_round: price, shipping_rating }; \
                }); \
            }")
        except PlaywrightTimeoutError:
            browser.close()
            return []
        browser.close()

    return data
