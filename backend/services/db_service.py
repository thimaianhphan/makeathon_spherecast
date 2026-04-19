"""
Database service for Agnes — AI Supply Chain Manager.
Responsible for all SQLite access.
"""

from __future__ import annotations

import sqlite3
from backend.config import SQLITE_DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a connection with row_factory = sqlite3.Row."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_all_companies() -> list[dict]:
    """Return all companies."""
    with get_connection() as conn:
        rows = conn.execute("SELECT Id, Name FROM Company ORDER BY Id").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_finished_goods(company_id: int | None = None) -> list[dict]:
    """Return all products where Type = 'finished-good', optionally filtered by company."""
    with get_connection() as conn:
        if company_id is not None:
            rows = conn.execute(
                "SELECT p.Id, p.SKU, p.SKU AS Name, p.CompanyId, p.Type, c.Name AS CompanyName "
                "FROM Product p JOIN Company c ON p.CompanyId = c.Id "
                "WHERE p.Type = 'finished-good' AND p.CompanyId = ? ORDER BY p.Id",
                (company_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT p.Id, p.SKU, p.SKU AS Name, p.CompanyId, p.Type, c.Name AS CompanyName "
                "FROM Product p JOIN Company c ON p.CompanyId = c.Id "
                "WHERE p.Type = 'finished-good' ORDER BY p.Id"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_bom_for_product(product_id: int) -> dict | None:
    """
    Return the BOM for a finished good including all BOM_Components
    joined to their raw-material Product records.
    """
    with get_connection() as conn:
        bom_row = conn.execute(
            "SELECT b.Id AS bom_id, p.Id AS prod_id, p.SKU, p.SKU AS Name, p.CompanyId "
            "FROM BOM b JOIN Product p ON b.ProducedProductId = p.Id "
            "WHERE b.ProducedProductId = ?",
            (product_id,),
        ).fetchone()
        if not bom_row:
            return None
        bom = _row_to_dict(bom_row)
        component_rows = conn.execute(
            "SELECT p.Id AS product_id, p.SKU, p.SKU AS Name "
            "FROM BOM_Component bc JOIN Product p ON bc.ConsumedProductId = p.Id "
            "WHERE bc.BOMId = ?",
            (bom["bom_id"],),
        ).fetchall()
    return {
        "bom_id": bom["bom_id"],
        "produced_product": {
            "id": bom["prod_id"],
            "sku": bom["SKU"],
            "name": bom["Name"],
            "company_id": bom["CompanyId"],
        },
        "components": [_row_to_dict(r) for r in component_rows],
    }


def get_all_boms_with_components() -> list[dict]:
    """Return every BOM with its components, joined to company info."""
    with get_connection() as conn:
        bom_rows = conn.execute(
            "SELECT b.Id AS bom_id, p.Id AS product_id, p.SKU, p.SKU AS Name, "
            "p.CompanyId, c.Name AS company_name "
            "FROM BOM b "
            "JOIN Product p ON b.ProducedProductId = p.Id "
            "JOIN Company c ON p.CompanyId = c.Id "
            "ORDER BY b.Id"
        ).fetchall()
        result = []
        for bom_row in bom_rows:
            bom = _row_to_dict(bom_row)
            component_rows = conn.execute(
                "SELECT p.Id AS product_id, p.SKU, p.SKU AS Name "
                "FROM BOM_Component bc JOIN Product p ON bc.ConsumedProductId = p.Id "
                "WHERE bc.BOMId = ?",
                (bom["bom_id"],),
            ).fetchall()
            result.append({
                "bom_id": bom["bom_id"],
                "produced_product": {
                    "id": bom["product_id"],
                    "sku": bom["SKU"],
                    "name": bom["Name"],
                    "company_id": bom["CompanyId"],
                    "company_name": bom["company_name"],
                },
                "components": [_row_to_dict(c) for c in component_rows],
            })
    return result


def get_supplier_product_mappings() -> list[dict]:
    """
    Return all Supplier_Product rows joined to Supplier and Product.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT sp.SupplierId AS supplier_id, s.Name AS supplier_name, "
            "sp.ProductId AS product_id, p.SKU AS product_sku, p.SKU AS product_name "
            "FROM Supplier_Product sp "
            "JOIN Supplier s ON sp.SupplierId = s.Id "
            "JOIN Product p ON sp.ProductId = p.Id "
            "ORDER BY sp.SupplierId, sp.ProductId"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_suppliers_for_product(product_id: int) -> list[dict]:
    """Return all suppliers that offer a specific raw material."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.Id AS supplier_id, s.Name AS supplier_name "
            "FROM Supplier_Product sp JOIN Supplier s ON sp.SupplierId = s.Id "
            "WHERE sp.ProductId = ? ORDER BY s.Id",
            (product_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_cross_company_demand() -> list[dict]:
    """
    Aggregate: for each raw material, which companies/BOMs/finished goods consume it.
    Used to identify consolidation opportunities.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT p.Id AS product_id, p.SKU AS product_name, "
            "COUNT(DISTINCT b.Id) AS bom_count, "
            "COUNT(DISTINCT fp.CompanyId) AS company_count "
            "FROM BOM_Component bc "
            "JOIN Product p ON bc.ConsumedProductId = p.Id "
            "JOIN BOM b ON bc.BOMId = b.Id "
            "JOIN Product fp ON b.ProducedProductId = fp.Id "
            "GROUP BY p.Id, p.SKU "
            "ORDER BY bom_count DESC, p.SKU"
        ).fetchall()
        result = []
        for row in rows:
            r = _row_to_dict(row)
            # fetch consuming companies detail
            company_rows = conn.execute(
                "SELECT DISTINCT c.Id AS company_id, c.Name AS company_name "
                "FROM BOM_Component bc "
                "JOIN BOM b ON bc.BOMId = b.Id "
                "JOIN Product fp ON b.ProducedProductId = fp.Id "
                "JOIN Company c ON fp.CompanyId = c.Id "
                "WHERE bc.ConsumedProductId = ?",
                (r["product_id"],),
            ).fetchall()
            r["consuming_companies"] = [_row_to_dict(cr) for cr in company_rows]
            result.append(r)
    return result


def ensure_price_cache_table() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Supplier_Price_Cache (
                supplier_id         INTEGER NOT NULL,
                product_id          INTEGER NOT NULL,
                material_name       TEXT,
                unit_price_eur      REAL,
                currency_original   TEXT,
                moq                 INTEGER,
                lead_time_days      INTEGER,
                certifications_json TEXT,
                country_of_origin   TEXT,
                red_flags_json      TEXT,
                source_urls_json    TEXT,
                source_type         TEXT NOT NULL,
                confidence          REAL NOT NULL,
                fetched_at          TEXT NOT NULL,
                PRIMARY KEY (supplier_id, product_id)
            )
        """)
        conn.commit()


def get_raw_materials() -> list[dict]:
    """Return all products where Type = 'raw-material'."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT p.Id, p.SKU, p.SKU AS Name, p.CompanyId, p.Type, c.Name AS CompanyName "
            "FROM Product p JOIN Company c ON p.CompanyId = c.Id "
            "WHERE p.Type = 'raw-material' ORDER BY p.Id"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
