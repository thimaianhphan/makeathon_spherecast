ALLOWED_SUPPLIER_URLS = [
    "https://www.bulksupplements.com/collections/new-products?page=1",
    "https://eu.capsuline.com/collections/bulk",
    "https://www.customprobiotics.com/single-strain-probiotics.html?CatListingOffset=12&Offset=12&Per_Page=12&Sort_By=disp_order",
    "https://feedsforless.com/collections/nutra-blend",
    "https://purebulk.com/pages/all-products-a-to-z",
    "https://www.source-omega.com/shop/omega-3--122.htm",
    "https://www.spectrumchemical.com/chemical",
    "https://www.traceminerals.com/collections/all",
]

ALLOWED_DOMAINS = {
    "www.bulksupplements.com",
    "eu.capsuline.com",
    "www.customprobiotics.com",
    "feedsforless.com",
    "purebulk.com",
    "www.source-omega.com",
    "www.spectrumchemical.com",
    "www.traceminerals.com",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SUPPLIER_ALLOWLIST = {
    "BulkSupplements": {
        "official_domain": "www.bulksupplements.com",
        "official_url": "https://www.bulksupplements.com/collections/new-products?page=1",
    },
    "Capsuline": {
        "official_domain": "eu.capsuline.com",
        "official_url": "https://eu.capsuline.com/collections/bulk",
    },
    "Custom Probiotics": {
        "official_domain": "www.customprobiotics.com",
        "official_url": "https://www.customprobiotics.com/single-strain-probiotics.html?CatListingOffset=12&Offset=12&Per_Page=12&Sort_By=disp_order",
    },
    "FeedsForLess": {
        "official_domain": "feedsforless.com",
        "official_url": "https://feedsforless.com/collections/nutra-blend",
    },
    "PureBulk": {
        "official_domain": "purebulk.com",
        "official_url": "https://purebulk.com/pages/all-products-a-to-z",
    },
    "Source-Omega": {
        "official_domain": "www.source-omega.com",
        "official_url": "https://www.source-omega.com/shop/omega-3--122.htm",
    },
    "Spectrum Chemical": {
        "official_domain": "www.spectrumchemical.com",
        "official_url": "https://www.spectrumchemical.com/chemical",
    },
    "Trace Minerals": {
        "official_domain": "www.traceminerals.com",
        "official_url": "https://www.traceminerals.com/collections/all",
    },
}

OFFICIAL_REGULATIONS = [
    {
        "rule_id": "EU_FIC_1169_2011",
        "jurisdiction": "EU",
        "title": "Regulation (EU) No 1169/2011 on the provision of food information to consumers",
        "source_type": "official_regulation",
        "source_url": "https://eur-lex.europa.eu/eli/reg/2011/1169/oj/eng",
        "text": (
            "Food information must not mislead consumers. "
            "Mandatory food information must be available for regulated products. "
            "Substances or products causing allergies or intolerances must be indicated "
            "where applicable."
        ),
    },
    {
        "rule_id": "CODEX_GPFH_HACCP",
        "jurisdiction": "International",
        "title": "Codex General Principles of Food Hygiene (CXC 1-1969) with HACCP",
        "source_type": "official_guidance",
        "source_url": "https://openknowledge.fao.org/server/api/core/bitstreams/6866dc55-d2c0-48dd-a528-a4d634f1b0b4/content",
        "text": (
            "Food safety management should be based on good hygiene practices and HACCP principles. "
            "Hazards can be biological, chemical, or physical, and food businesses should identify, "
            "evaluate, and control significant hazards."
        ),
    },
]

WEBSITE_EVIDENCE_KEYWORDS = {
    "allergen_terms": [
        "soy", "milk", "dairy", "whey", "egg", "gluten", "wheat",
        "tree nut", "nuts", "peanut", "fish", "shellfish", "sesame"
    ],
    "animal_terms": [
        "bovine", "gelatin", "gelatine", "fish oil", "animal",
        "collagen", "beef", "porcine", "softgel"
    ],
    "plant_terms": [
        "vegan", "vegetarian", "sunflower", "soy", "plant-based",
        "cellulose capsule", "veggie capsule"
    ],
    "quality_terms": [
        "food grade", "food-grade", "usp", "pharmaceutical grade",
        "lab tested", "third party tested", "certificate", "coa",
        "analysis", "haccp", "iso", "organic", "non-gmo", "gmp"
    ],
    "warning_terms": [
        "artificial", "flavor", "flavour", "sweetener",
        "stabilizer", "preservative", "blend", "proprietary"
    ]
}

ALLERGEN_TERMS = {
    "soy", "milk", "dairy", "whey", "egg", "gluten",
    "wheat", "nuts", "peanut", "fish", "sesame"
}

HAZARD_TERMS = {
    "artificial", "sweetener", "preservative", "blend",
    "chemical", "food grade", "coa", "certificate"
}