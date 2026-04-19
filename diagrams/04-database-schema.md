# Database Schema (SQLite)

```mermaid
erDiagram
    Company {
        int    Id   PK
        string Name
    }

    Product {
        int    Id        PK
        string SKU
        string Name
        string Type      "finished-good | raw-material"
        int    CompanyId FK
    }

    BOM {
        int Id              PK
        int ProducedProductId FK
    }

    BOM_Component {
        int BOMId           FK
        int ConsumedProductId FK
    }

    Supplier {
        int    Id       PK
        string Name
        string Homepage
    }

    Supplier_Product {
        int    SupplierId   FK
        int    ProductId    FK
        float  Purity
        float  Quality
        float  QualityScore
        json   Compliance
        string ProcessedAt
    }

    Supplier_Product_Price {
        int    SupplierId    FK
        int    ProductId     FK
        float  Quantity
        string QuantityUnit
        float  Price
        string Currency
    }

    Company            ||--o{ Product            : "makes"
    Product            ||--o| BOM                : "produced by"
    BOM                ||--o{ BOM_Component      : "contains"
    BOM_Component      }o--|| Product            : "consumes"
    Supplier           ||--o{ Supplier_Product   : "supplies"
    Product            ||--o{ Supplier_Product   : "supplied as"
    Supplier_Product   ||--o{ Supplier_Product_Price : "priced at"
```

## File-Based Caches

| File | Contents | TTL |
|------|----------|-----|
| `data/evidence_cache.json` | Supplier evidence fetched during pipeline runs | TTL-based |
| `data/rm_classification.json` | Raw-material functional category classification | Persistent |
| `cascade_history.json` | Full past cascade reports | Persistent |
| Browser `localStorage` | Analysis results, user variant selections | Persistent |