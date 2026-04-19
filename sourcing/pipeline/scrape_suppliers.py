import re
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DB_PATH       = Path(__file__).parent.parent / "data" / "db.sqlite"
OUT_DIR       = Path(__file__).parent.parent / "data" / "supplier_products"
CSV_PATH      = Path(__file__).parent.parent / "data" / "fully_sourced_products_with_links.csv"
OVERVIEW_PATH = Path(__file__).parent.parent / "data" / "supplier_products_overview_pages.txt"
DELAY         = 1.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DOMAIN_TO_SUPPLIER: dict[str, str] = {
    "bulksupplements":  "BulkSupplements",
    "capsuline":        "Capsuline",
    "customprobiotics": "Custom Probiotics",
    "feedsforless":     "Nutra Blend",
    "purebulk":         "PureBulk",
    "source-omega":     "Source-Omega LLC",
    "spectrumchemical": "Spectrum Chemical",
    "traceminerals":    "Trace Minerals",
}


def load_db_lookup() -> tuple[dict[tuple[str, str], tuple[int, int]], dict[str, list[dict]]]:
    """Returns (lookup, by_supplier) built from the DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT sp.SupplierId, s.Name AS SupplierName, sp.ProductId, p.SKU
        FROM Supplier_Product sp
        JOIN Supplier s ON s.Id = sp.SupplierId
        JOIN Product  p ON p.Id = sp.ProductId
    """).fetchall()
    conn.close()

    lookup: dict[tuple[str, str], tuple[int, int]] = {}
    by_supplier: dict[str, list[dict]] = {}
    for r in rows:
        key = (r["SupplierName"], r["SKU"])
        val = (r["SupplierId"], r["ProductId"])
        lookup[key] = val
        by_supplier.setdefault(r["SupplierName"], []).append({
            "SupplierId": r["SupplierId"], "ProductId": r["ProductId"],
            "SKU": r["SKU"], "SupplierName": r["SupplierName"],
        })
    return lookup, by_supplier


def fetch(url: str, session: requests.Session) -> requests.Response | None:
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN: {url} → {e}")
        return None


def sku_to_ingredient(sku: str) -> str:
    m = re.match(r"^(?:RM|FG)-C\d+-(.+)-[0-9a-f]{8}$", sku)
    return m.group(1).replace("-", " ").lower() if m else sku.lower()


def best_match(title: str, candidates: list[dict], threshold: float = 0.45) -> dict | None:
    best, best_score = None, threshold
    title_norm = title.lower()
    for p in candidates:
        ingredient = sku_to_ingredient(p["SKU"])
        score = SequenceMatcher(None, ingredient, title_norm).ratio()
        if ingredient in title_norm or title_norm in ingredient:
            score = max(score, 0.7)
        if score > best_score:
            best_score, best = score, p
    return best


def product_urls_shopify(catalog_url: str, session: requests.Session) -> list[str]:
    parsed = urlparse(catalog_url)
    base   = f"{parsed.scheme}://{parsed.netloc}"
    parts  = [p for p in parsed.path.strip("/").split("/") if p]
    collection = parts[parts.index("collections") + 1] if "collections" in parts else "all"
    urls, page = [], 1
    while True:
        resp = fetch(f"{base}/collections/{collection}/products.json?limit=250&page={page}", session)
        if not resp:
            break
        products = resp.json().get("products", [])
        if not products:
            break
        urls += [f"{base}/products/{p['handle']}" for p in products if p.get("handle")]
        page += 1
        time.sleep(DELAY)
    return urls


def product_urls_generic(catalog_url: str, session: requests.Session) -> list[str]:
    resp = fetch(catalog_url, session)
    if not resp:
        return []
    soup   = BeautifulSoup(resp.text, "html.parser")
    parsed = urlparse(catalog_url)
    base   = f"{parsed.scheme}://{parsed.netloc}"
    skip   = ("/cart", "/checkout", "/account", "/login", "/search",
              "/blog", "/news", "/contact", "/about", "/policy", "/faq")
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base, a["href"].split("?")[0].split("#")[0])
        fp   = urlparse(full)
        path = fp.path.rstrip("/")
        if fp.netloc != parsed.netloc or any(path.startswith(s) for s in skip):
            continue
        if full not in seen and len([s for s in path.split("/") if s]) >= 2:
            seen.add(full)
            links.append(full)
    return links


_STRIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}
_PRODUCT_SELECTORS = [
    "main", "article",
    "[class*='product']", "[id*='product']",
    "[class*='content']", "[role='main']",
]


def extract_content(soup: BeautifulSoup) -> str:
    """
    Returns cleaned HTML focused on product content.
    Tries product/main content selectors first; falls back to full body.
    Always strips scripts, styles, nav, header, footer, etc.
    """
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    for selector in _PRODUCT_SELECTORS:
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 200:
            return str(node)

    body = soup.find("body")
    return str(body) if body else str(soup)


def get_page_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    tag = soup.find("title")
    return tag.get_text(strip=True).split("|")[0].strip() if tag else ""


def load_overview_urls() -> dict[str, str]:
    """Returns {supplier_name: catalog_url} from supplier_products_overview_pages.txt."""
    result: dict[str, str] = {}
    for line in OVERVIEW_PATH.read_text().splitlines():
        url = line.strip()
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        for keyword, name in DOMAIN_TO_SUPPLIER.items():
            if keyword in host:
                result[name] = url
                break
    return result
