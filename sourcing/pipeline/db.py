import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db.sqlite"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    existing_supplier = {r[1] for r in conn.execute("PRAGMA table_info(Supplier)")}
    if "Homepage" not in existing_supplier:
        conn.execute("ALTER TABLE Supplier ADD COLUMN Homepage TEXT")
    existing = {r[1] for r in conn.execute("PRAGMA table_info(Supplier_Product)")}
    for col, ddl in [
        ("Purity",      "REAL"),
        ("Quality",     "TEXT"),
        ("QualityScore","REAL"),
        ("Compliance",  "TEXT"),
        ("ProcessedAt", "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE Supplier_Product ADD COLUMN {col} {ddl}")
    existing_price = {r[1] for r in conn.execute("PRAGMA table_info(Supplier_Product_Price)")}
    if not existing_price:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Supplier_Product_Price (
                SupplierId   INTEGER NOT NULL,
                ProductId    INTEGER NOT NULL,
                Quantity     REAL,
                QuantityUnit TEXT,
                Price        REAL    NOT NULL,
                Currency     TEXT    NOT NULL DEFAULT 'USD',
                PRIMARY KEY (SupplierId, ProductId, Quantity, QuantityUnit)
            )
        """)


def _normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())


def search_supplier(query: str) -> list[dict]:
    """Case-insensitive search ignoring spaces and punctuation."""
    norm = _normalize(query)
    with _conn() as conn:
        suppliers = [dict(r) for r in conn.execute("SELECT * FROM Supplier ORDER BY Name")]
    return [s for s in suppliers if norm in _normalize(s["Name"]) or _normalize(s["Name"]) in norm]


def set_supplier_homepage(supplier_id: int, homepage: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE Supplier SET Homepage = ? WHERE Id = ?", (homepage, supplier_id))


def get_companies() -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM Company ORDER BY Name")]


def get_products(type: str | None = None) -> list[dict]:
    with _conn() as conn:
        if type:
            rows = conn.execute(
                "SELECT p.*, c.Name AS CompanyName FROM Product p JOIN Company c ON c.Id = p.CompanyId WHERE p.Type = ? ORDER BY p.SKU",
                (type,),
            )
        else:
            rows = conn.execute(
                "SELECT p.*, c.Name AS CompanyName FROM Product p JOIN Company c ON c.Id = p.CompanyId ORDER BY p.SKU"
            )
        return [dict(r) for r in rows]


def get_boms() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT b.Id AS BOMId, p.SKU AS ProducedSKU, c.Name AS CompanyName
            FROM BOM b
            JOIN Product p ON p.Id = b.ProducedProductId
            JOIN Company c ON c.Id = p.CompanyId
            ORDER BY p.SKU
            """
        )
        return [dict(r) for r in rows]


def get_bom_components(bom_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT bc.BOMId, p.SKU AS ConsumedSKU, p.Type, c.Name AS CompanyName
            FROM BOM_Component bc
            JOIN Product p ON p.Id = bc.ConsumedProductId
            JOIN Company c ON c.Id = p.CompanyId
            WHERE bc.BOMId = ?
            ORDER BY p.SKU
            """,
            (bom_id,),
        )
        return [dict(r) for r in rows]


def get_suppliers() -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM Supplier ORDER BY Name")]


def get_supplier_products(supplier_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if supplier_id:
            rows = conn.execute(
                """
                SELECT sp.SupplierId, s.Name AS SupplierName, p.SKU, p.Type, c.Name AS CompanyName
                FROM Supplier_Product sp
                JOIN Supplier s ON s.Id = sp.SupplierId
                JOIN Product p ON p.Id = sp.ProductId
                JOIN Company c ON c.Id = p.CompanyId
                WHERE sp.SupplierId = ?
                ORDER BY p.SKU
                """,
                (supplier_id,),
            )
        else:
            rows = conn.execute(
                """
                SELECT sp.SupplierId, s.Name AS SupplierName, p.SKU, p.Type, c.Name AS CompanyName
                FROM Supplier_Product sp
                JOIN Supplier s ON s.Id = sp.SupplierId
                JOIN Product p ON p.Id = sp.ProductId
                JOIN Company c ON c.Id = p.CompanyId
                ORDER BY s.Name, p.SKU
                """
            )
        return [dict(r) for r in rows]


def _ingredient_name(sku: str) -> str:
    """Extract the ingredient slug from RM-CXX-<name>-<8hex> SKUs."""
    m = re.match(r"RM-C\d+-(.+)-[0-9a-f]{8}$", sku)
    return m.group(1) if m else sku


def _equiv_map(bom_skus: set[str], supplier_skus: set[str]) -> dict[str, str]:
    """
    Returns {supplier_sku: bom_sku} for every supplier SKU whose ingredient name
    matches a BOM component ingredient name (same ingredient, different company/hash).
    Exact-match SKUs are included too, so the map is the complete coverage lookup.
    """
    bom_by_name: dict[str, str] = {}
    for sku in bom_skus:
        bom_by_name[_ingredient_name(sku)] = sku  # last writer wins; names are unique per BOM
    result: dict[str, str] = {}
    for sku in supplier_skus:
        bom_sku = bom_by_name.get(_ingredient_name(sku))
        if bom_sku:
            result[sku] = bom_sku
    return result


def batch(product_sku: str, filters: list | None = None) -> dict:
    """
    Assigns BOM components to the fewest possible suppliers using greedy set cover.
    Input is the SKU of the produced (finished-good) component.

    filters: optional list of callables from filter_products (price_filter, purity_filter, etc.).
             When provided, only supplier-product pairs passing all filters are eligible.

    Returns:
        assignments: {sku: {"supplier": name, "prices": [...], "purity": ..., "quality": ...,
                            "quality_score": ..., "compliance": {...}}}
        uncovered:   SKUs with no available supplier (after filters)
        suppliers:   ordered list of chosen supplier names
    """
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT b.Id AS BOMId
            FROM BOM b
            JOIN Product p ON p.Id = b.ProducedProductId
            WHERE p.SKU = ?
            """,
            (product_sku,),
        ).fetchone()

    if not row:
        return {"assignments": {}, "uncovered": [], "suppliers": []}

    bom_id = row["BOMId"]
    components = get_bom_components(bom_id)
    if not components:
        return {"assignments": {}, "uncovered": [], "suppliers": []}

    skus = {c["ConsumedSKU"] for c in components}

    # Build full enriched list (all supplier products), not just exact SKU matches,
    # so equivalent products (same ingredient name, different company/hash) can cover BOM components.
    all_enriched = get_supplier_products_enriched()
    all_sp_skus = {p["sku"] for p in all_enriched}
    equiv = _equiv_map(skus, all_sp_skus)  # supplier_sku → bom_sku

    if filters:
        eligible = [p for p in all_enriched if p["sku"] in equiv]
        for f in filters:
            eligible = [p for p in eligible if f(p)]
    else:
        eligible = [p for p in all_enriched if p["sku"] in equiv]

    # Map supplier → set of BOM SKUs they can cover (via exact or equivalent products)
    supplier_skus: dict[str, set[str]] = {}
    # supplier → bom_sku → best detail (prefer exact match over equivalent)
    supplier_details: dict[str, dict[str, dict]] = {}
    for p in eligible:
        sp_sku = p["sku"]
        bom_sku = equiv[sp_sku]
        name = p["supplier_name"]
        supplier_skus.setdefault(name, set()).add(bom_sku)
        detail = {
            "prices": p.get("prices") or [],
            "purity": p.get("purity"),
            "quality": p.get("quality"),
            "quality_score": p.get("quality_score"),
            "compliance": p.get("compliance") or {},
            "sourced_sku": sp_sku,  # actual supplier product used
        }
        # Prefer exact-match SKU over equivalent
        existing = supplier_details.get(name, {}).get(bom_sku)
        if existing is None or (sp_sku == bom_sku and existing.get("sourced_sku") != bom_sku):
            supplier_details.setdefault(name, {})[bom_sku] = detail

    uncovered = set(skus)
    assignments: dict[str, dict] = {}
    chosen_suppliers: list[str] = []

    while uncovered:
        best_supplier = max(
            supplier_skus,
            key=lambda s: len(supplier_skus[s] & uncovered),
            default=None,
        )
        if best_supplier is None or not (supplier_skus[best_supplier] & uncovered):
            break
        covered_now = supplier_skus[best_supplier] & uncovered
        for sku in covered_now:
            detail = (supplier_details.get(best_supplier) or {}).get(sku) or {}
            assignments[sku] = {"supplier": best_supplier, **detail}
        chosen_suppliers.append(best_supplier)
        uncovered -= covered_now
        del supplier_skus[best_supplier]

    return {
        "assignments": assignments,
        "uncovered": sorted(uncovered),
        "suppliers": chosen_suppliers,
    }


def get_supplier_products_enriched() -> list[dict]:
    """Returns each (supplier, product) pair with nested price tiers and purity/quality."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT sp.SupplierId, sp.ProductId, s.Name AS SupplierName,
                   p.SKU, sp.Purity, sp.Quality, sp.QualityScore, sp.Compliance,
                   spp.Quantity, spp.QuantityUnit, spp.Price, spp.Currency
            FROM Supplier_Product sp
            JOIN Supplier s ON s.Id = sp.SupplierId
            JOIN Product p ON p.Id = sp.ProductId
            LEFT JOIN Supplier_Product_Price spp
                   ON spp.SupplierId = sp.SupplierId AND spp.ProductId = sp.ProductId
            ORDER BY sp.SupplierId, sp.ProductId
            """
        )
        products: dict[tuple, dict] = {}
        for row in rows:
            key = (row["SupplierId"], row["ProductId"])
            if key not in products:
                products[key] = {
                    "supplier_id": row["SupplierId"],
                    "product_id": row["ProductId"],
                    "supplier_name": row["SupplierName"],
                    "sku": row["SKU"],
                    "purity": row["Purity"],
                    "quality": row["Quality"],
                    "quality_score": row["QualityScore"],
                    "compliance": json.loads(row["Compliance"]) if row["Compliance"] else {},
                    "prices": [],
                }
            if row["Price"] is not None:
                products[key]["prices"].append({
                    "quantity": row["Quantity"],
                    "unit": row["QuantityUnit"],
                    "price": row["Price"],
                    "currency": row["Currency"],
                })
        return list(products.values())


def upsert_supplier_product_prices(supplier_id: int, product_id: int, prices: list[dict]) -> None:
    """Replaces all price tiers for a (supplier, product) pair."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM Supplier_Product_Price WHERE SupplierId = ? AND ProductId = ?",
            (supplier_id, product_id),
        )
        for p in prices:
            conn.execute(
                """INSERT INTO Supplier_Product_Price (SupplierId, ProductId, Quantity, QuantityUnit, Price, Currency)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (supplier_id, product_id, p.get("quantity"), p.get("unit"), p["price"], p.get("currency", "USD")),
            )


def get_processed_supplier_products() -> set[tuple[int, int]]:
    """Returns (SupplierId, ProductId) pairs that have already been processed."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT SupplierId, ProductId FROM Supplier_Product WHERE ProcessedAt IS NOT NULL"
        )
        return {(r["SupplierId"], r["ProductId"]) for r in rows}


def upsert_supplier_product_info(
    supplier_id: int,
    product_id: int,
    purity: float | None,
    quality: str | None,
    quality_score: float | None = None,
    compliance: dict | None = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            """UPDATE Supplier_Product
               SET Purity = ?, Quality = ?, QualityScore = ?, Compliance = ?, ProcessedAt = datetime('now')
               WHERE SupplierId = ? AND ProductId = ?""",
            (purity, quality, quality_score, json.dumps(compliance) if compliance else None, supplier_id, product_id),
        )


def check_compliance(
    skus: list[str],
    quality: dict[str, str] | None = None,
) -> list[dict]:
    """
    Checks each SKU for: existence, raw-material type, and at least one supplier.

    quality maps SKU -> required quality label. Because quality is not stored in
    the DB, a required quality is recorded in the result but cannot be verified
    against supplier data (status set to "quality-unverifiable" when provided).

    Returns a list of per-SKU compliance records.
    """
    if not skus:
        return []

    placeholders = ",".join("?" * len(skus))

    with _conn() as conn:
        product_rows = {
            r["SKU"]: dict(r)
            for r in conn.execute(
                f"SELECT SKU, Type FROM Product WHERE SKU IN ({placeholders})",
                skus,
            )
        }
        supplier_rows = conn.execute(
            f"""
            SELECT p.SKU, COUNT(sp.SupplierId) AS SupplierCount
            FROM Product p
            JOIN Supplier_Product sp ON sp.ProductId = p.Id
            WHERE p.SKU IN ({placeholders})
            GROUP BY p.SKU
            """,
            skus,
        )
        supplier_counts: dict[str, int] = {r["SKU"]: r["SupplierCount"] for r in supplier_rows}

    results = []
    for sku in skus:
        required_quality = (quality or {}).get(sku)
        if sku not in product_rows:
            results.append({"sku": sku, "compliant": False, "reason": "not found", "required_quality": required_quality})
            continue

        product = product_rows[sku]
        if product["Type"] != "raw-material":
            results.append({"sku": sku, "compliant": False, "reason": "not a raw-material", "required_quality": required_quality})
            continue

        count = supplier_counts.get(sku, 0)
        if count == 0:
            results.append({"sku": sku, "compliant": False, "reason": "no supplier", "required_quality": required_quality})
            continue

        if required_quality:
            results.append({"sku": sku, "compliant": True, "reason": "quality-unverifiable", "required_quality": required_quality, "supplier_count": count})
        else:
            results.append({"sku": sku, "compliant": True, "reason": None, "required_quality": None, "supplier_count": count})

    return results
