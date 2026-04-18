import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db.sqlite"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


def batch(product_sku: str) -> dict:
    """
    Assigns BOM components to the fewest possible suppliers using greedy set cover.
    Input is the SKU of the produced (finished-good) component.

    Returns:
        assignments: {sku: supplier_name} for each covered component
        uncovered:   SKUs with no available supplier
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

    skus = [c["ConsumedSKU"] for c in components]
    placeholders = ",".join("?" * len(skus))

    with _conn() as conn:
        rows = conn.execute(
            f"""
            SELECT p.SKU, s.Name AS SupplierName
            FROM Supplier_Product sp
            JOIN Supplier s ON s.Id = sp.SupplierId
            JOIN Product p ON p.Id = sp.ProductId
            WHERE p.SKU IN ({placeholders})
            ORDER BY s.Name
            """,
            skus,
        )
        supplier_skus: dict[str, set[str]] = {}
        for r in rows:
            supplier_skus.setdefault(r["SupplierName"], set()).add(r["SKU"])

    uncovered = set(skus)
    assignments: dict[str, str] = {}
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
            assignments[sku] = best_supplier
        chosen_suppliers.append(best_supplier)
        uncovered -= covered_now
        del supplier_skus[best_supplier]

    return {
        "assignments": assignments,
        "uncovered": sorted(uncovered),
        "suppliers": chosen_suppliers,
    }


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
