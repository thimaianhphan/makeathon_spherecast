"""Product catalogue service — loads finished goods from the SQLite database."""

from __future__ import annotations

from backend.schemas import CatalogueProduct
from backend.services.db_service import get_finished_goods


class CatalogueService:
    """Catalogue backed by the SQLite Product table (finished-good rows)."""

    def list_all(self) -> list[CatalogueProduct]:
        rows = get_finished_goods()
        return [self._row_to_product(r) for r in rows]

    def get(self, product_id: str) -> CatalogueProduct | None:
        rows = get_finished_goods()
        for r in rows:
            if str(r["Id"]) == product_id:
                return self._row_to_product(r)
        return None

    def get_intent_for_product(self, product: CatalogueProduct, quantity: int) -> str:
        if quantity == 1:
            return f"Source all ingredients required to manufacture one unit of {product.name}"
        return f"Source all ingredients required to manufacture {quantity} units of {product.name}"

    @staticmethod
    def _row_to_product(row: dict) -> CatalogueProduct:
        company = row.get("CompanyName", "")
        return CatalogueProduct(
            product_id=str(row["Id"]),
            name=row["Name"],
            description=company,
            selling_price_eur=0.0,
            intent_template="Source all ingredients required to manufacture one unit of {name}",
            currency="EUR",
        )


# Global singleton
catalogue_service = CatalogueService()
