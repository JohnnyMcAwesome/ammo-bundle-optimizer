import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urlencode
from typing import List, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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
    search_terms: Optional[List[str]] = None
) -> str:
    key = caliber.lower().replace(" ", "")
    slug = CALIBER_SLUGS.get(key, caliber)
    params = {}
    if bullet_weight is not None:
        params["grains"] = bullet_weight
    if search_terms:
        params["search"] = " ".join(search_terms)
    query = urlencode(params)
    return f"{BASE_URL}{slug}?{query}" if query else f"{BASE_URL}{slug}"


def parse_search_results(html: str) -> List[dict]:
    tree = HTMLParser(html)
    rows = tree.css("tr[data-productid]")
    results: List[dict] = []

    for row in rows:
        logo = row.css_first("td.logo-cell img")
        retailer = logo.attributes.get("alt") if logo else None

        price_el = row.css_first("td.price-cell")
        price_text = price_el.text(strip=True) if price_el else ""
        price = None
        if price_text.startswith("$"):
            try:
                price = float(price_text.replace("$", "").split("/")[0])
            except ValueError:
                continue

        ship_el = row.css_first("td.shipping-cell span.rating")
        shipping_rating = None
        if ship_el:
            try:
                shipping_rating = int(ship_el.text(strip=True))
            except ValueError:
                shipping_rating = None

        link = row.css_first("td.description-cell a")
        href = link.attributes.get('href') if link else None
        product_url = f"https://ammoseek.com{href}" if href else None
        title = link.text(strip=True) if link else None

        results.append({
            "retailer": retailer,
            "price_per_round": price,
            "shipping_rating": shipping_rating,
            "product_url": product_url,
            "title": title,
        })

    return results


def scrape_ammoseek(
    caliber: str,
    bullet_weight: Optional[int] = None,
    search_terms: Optional[List[str]] = None
) -> List[dict]:
    url = build_search_url(caliber, bullet_weight, search_terms)
    print(f"Scraping: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        )
        try:
            page.goto(url, timeout=30000)
            # Disable compact view to load full results if present
            try:
                compact_toggle = page.query_selector("text=Compact Results")
                if compact_toggle:
                    compact_toggle.click()
            except Exception:
                pass
            # Wait for results to load
            page.wait_for_selector('tr[data-productid]', timeout=15000)
        except PlaywrightTimeoutError:
            browser.close()
            return []
        html = page.content()
        browser.close()

    return parse_search_results(html)
