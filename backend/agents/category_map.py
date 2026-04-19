# CPG ingredient functional categories
# Maps category name → primary agent responsible
CATEGORY_AGENT_MAP = {
    "emulsifiers": "supplier-cargill-food-ingredients",
    "sweeteners": "supplier-tereos-s-a",
    "fats_oils": "supplier-aak-ab",
    "flavourings": "supplier-international-flavors-fragrances",
    "preservatives": "supplier-brenntag-se",
    "antioxidants": "supplier-dsm-firmenich",
    "proteins": "supplier-adm-specialty-ingredients",
    "starches": "supplier-roquette-fr-res",
    "acids": "supplier-brenntag-se",
    "vitamins": "supplier-dsm-firmenich",
    "colourants": "supplier-dsm-firmenich",
    "leavening": "supplier-brenntag-se",
    "minerals": "supplier-brenntag-se",
    "other": "supplier-cargill-food-ingredients",
}

# CPG ingredient categories list (for LLM classification)
CPG_INGREDIENT_CATEGORIES = [
    "emulsifiers",
    "sweeteners",
    "fats_oils",
    "flavourings",
    "preservatives",
    "antioxidants",
    "proteins",
    "starches",
    "acids",
    "vitamins",
    "colourants",
    "leavening",
    "minerals",
    "other",
]
