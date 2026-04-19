# Sourcing Pipeline

Greedy supplier batching for finished-good BOMs — assigns every raw-material component to the fewest possible suppliers, with optional quality/price filters and LLM-based evaluation.

## What it does

Given a finished-good SKU, the pipeline:

1. **Looks up the BOM** — finds all raw-material component SKUs for that product.
2. **Runs greedy set-cover** (`db.batch()`) — picks the smallest set of suppliers that collectively cover every component, maximising overlap.
3. **Applies filters** (optional) — price range, purity, quality score, compliance metrics. Suppliers that fail any filter are excluded before the set-cover step.
4. **Evaluates assignments** (optional) — an LLM judge (Gemini via DeepEval GEval) scores each assignment against the supplier's scraped product page.

## Structure

```
sourcing/
├── pipeline/
│   ├── db.py                                  # SQLite access + batch() + migrations
│   ├── filter_products.py                     # Composable filter factories
│   ├── generate_synthetic_product_qualities.py # Seed synthetic price tiers
│   ├── evaluate.py                            # LLM-as-judge evaluation (Gemini)
│   ├── text2product.py                        # HTML → structured product info (Gemini)
│   ├── scrape_suppliers.py                    # Supplier page scraping
│   ├── add_supplier_homepage.ipynb            # One-time: populate Supplier.Homepage
│   ├── batch_by_sku.ipynb                     # Interactive batching + evaluation
│   ├── add_product_information.ipynb          # Enrich supplier-product records
│   └── demo_database_use.ipynb               # DB exploration notebook
└── data/
    ├── db.sqlite                              # SQLite database
    ├── supplier_products/                     # Scraped HTML pages per supplier-product
    ├── supplier_products_overview_pages.txt   # Supplier homepage URLs
    ├── extracted_products.json
    └── compliance/                            # FDA/FTC regulatory PDFs
```

## Database schema

| Table | Key columns |
|---|---|
| `Supplier` | `Id`, `Name`, `Homepage` |
| `Product` | `Id`, `SKU`, `Type` (`raw-material` / finished-good) |
| `Supplier_Product` | `SupplierId`, `ProductId`, `Purity`, `Quality`, `QualityScore`, `Compliance` (JSON) |
| `Supplier_Product_Price` | `SupplierId`, `ProductId`, `Quantity`, `QuantityUnit`, `Price`, `Currency` |
| `BOM` / `BOM_Component` | Links finished-good → consumed raw-material SKUs |

## Quick start

```bash
cd sourcing
uv run python pipeline/generate_synthetic_product_qualities.py  # seed prices
# then open pipeline/batch_by_sku.ipynb
```

## API endpoint

`POST /api/sourcing/batch` — run batching from the frontend or programmatically.

```json
{
  "sku": "FG-amazon-b0002wrqy4",
  "price_max": 200.0,
  "purity_min": 0.95,
  "quality_min": 0.7
}
```
