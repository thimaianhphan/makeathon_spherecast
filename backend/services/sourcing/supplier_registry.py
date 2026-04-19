"""
supplier_registry.py
====================
Taxonomy of 40 suppliers classified by how accessible their price and
spec data is online.  Downstream code branches on ``tier`` to decide
whether to scrape, skip, or fetch spec-only data.

Tiers
-----
full        – price + spec visible on the supplier's own site; direct scrape viable.
full_3p     – price visible only via a third-party distributor page.
spec_only   – technical spec / datasheet online but no public price (RFQ required).
opaque      – portal-gated / custom RFQ / contract-manufacturing; nothing useful online.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Main registry
# Keys MUST match the ``Name`` column in the Supplier table (case-sensitive).
# ---------------------------------------------------------------------------

SUPPLIER_ACCESS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # FULL  (price + spec online, direct scrape viable)
    # ------------------------------------------------------------------
    "BulkSupplements": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.bulksupplements.com/",
        "search_pattern": "site:bulksupplements.com {material}",
        "infra": "E-commerce Direct",
    },
    "Capsuline": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://capsuline.com/",
        "search_pattern": "site:capsuline.com {material}",
        "infra": "E-commerce Direct",
    },
    "Custom Probiotics": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.customprobiotics.com/",
        "search_pattern": "site:customprobiotics.com {material}",
        "infra": "E-commerce Direct",
    },
    "Nutri Avenue": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.nutriavenue.com/",
        "search_pattern": "site:nutriavenue.com {material}",
        "infra": "E-commerce Direct",
    },
    "PureBulk": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://purebulk.com/",
        "search_pattern": "site:purebulk.com {material}",
        "infra": "E-commerce Direct",
    },
    "Source-Omega LLC": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.source-omega.com/",
        "search_pattern": "site:source-omega.com {material}",
        "infra": "E-commerce Direct",
    },
    "Spectrum Chemical": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.spectrumchemical.com/",
        "search_pattern": "site:spectrumchemical.com {material}",
        "infra": "E-commerce Direct",
    },
    "Trace Minerals": {
        "tier": "full",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://www.traceminerals.com/",
        "search_pattern": "site:traceminerals.com {material}",
        "infra": "E-commerce Direct",
    },
    # ------------------------------------------------------------------
    # FULL_3P  (price visible via third-party distributor)
    # ------------------------------------------------------------------
    "Nutra Blend": {
        "tier": "full_3p",
        "price_online": True,
        "spec_online": True,
        "base_url": "https://feedsforless.com/collections/nutra-blend",
        "search_pattern": "site:feedsforless.com {material} nutra-blend",
        "infra": "Third-Party Distributor",
    },
    # ------------------------------------------------------------------
    # SPEC_ONLY  (technical spec online, no public price)
    # ------------------------------------------------------------------
    "AIDP": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "American Botanicals": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Ashland": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Balchem": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Colorcon": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Darling Ingredients / Rousselot": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "FutureCeuticals": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "IFF": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Icelandirect": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Ingredion": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Jost Chemical": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Koster Keunen": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Magtein / ThreoTech LLC": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Mueggenburg USA": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Nutra Food Ingredients": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Prinova USA": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Specialty Enzymes & Probiotics": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Stauber": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Strahl & Pitsch": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "TCI America": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    "Univar Solutions": {
        "tier": "spec_only",
        "price_online": False,
        "spec_online": True,
        "base_url": None,
        "search_pattern": None,
        "infra": "Spec-Led Industrial",
    },
    # ------------------------------------------------------------------
    # OPAQUE  (portal-gated / custom RFQ / contract manufacturing)
    # ------------------------------------------------------------------
    "ADM": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Actus Nutrition": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Cambrex": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Cargill": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Gold Coast Ingredients": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Makers Nutrition": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Sawgrass Nutra Labs": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Sensient": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Virginia Dare": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
    "Vitaquest": {
        "tier": "opaque",
        "price_online": False,
        "spec_online": False,
        "base_url": None,
        "search_pattern": None,
        "infra": "Enterprise B2B",
    },
}

# ---------------------------------------------------------------------------
# Aliases: lowercased DB Name -> canonical SUPPLIER_ACCESS key
# Populated only for actual mismatches discovered via Step 1 DB query.
# All 40 DB names matched the taxonomy exactly, so this dict is empty.
# ---------------------------------------------------------------------------

ALIASES: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_access(supplier_name: str) -> dict | None:
    """Return the access descriptor for *supplier_name*, or None if unknown.

    Lookup is case-insensitive and trims surrounding whitespace.
    Checks ALIASES before the main registry.
    Callers should treat None as equivalent to tier="opaque".
    """
    if not supplier_name:
        return None
    name = supplier_name.strip()
    # Direct (case-sensitive) lookup first – fastest path.
    if name in SUPPLIER_ACCESS:
        return SUPPLIER_ACCESS[name]
    # Alias lookup (all aliases are lowercased).
    canonical = ALIASES.get(name.lower())
    if canonical:
        return SUPPLIER_ACCESS.get(canonical)
    # Case-insensitive fallback scan.
    lower = name.lower()
    for key in SUPPLIER_ACCESS:
        if key.lower() == lower:
            return SUPPLIER_ACCESS[key]
    return None


def is_opaque(supplier_name: str) -> bool:
    """Return True when the supplier is unknown or tier is 'opaque'."""
    info = get_access(supplier_name)
    if info is None:
        return True
    return info["tier"] == "opaque"


# ---------------------------------------------------------------------------
# Self-test (not run on import; call explicitly or via pytest)
# ---------------------------------------------------------------------------

def _selftest() -> None:
    """Assert that every supplier in the DB is covered by this registry."""
    import sqlite3
    import pathlib

    # Locate db.sqlite relative to this file: repo-root/data/db.sqlite
    # Path depth: supplier_registry.py -> sourcing -> services -> backend -> repo_root
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    db_path = repo_root / "data" / "db.sqlite"

    if not db_path.exists():
        raise FileNotFoundError(f"DB not found at {db_path}")

    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT Name FROM Supplier ORDER BY Id").fetchall()
    con.close()

    db_names = [r[0] for r in rows]
    covered = set(SUPPLIER_ACCESS.keys()) | set(ALIASES.values())
    alias_keys = set(ALIASES.keys())

    missing = []
    for db_name in db_names:
        in_registry = db_name in covered
        in_alias = db_name.lower() in alias_keys
        if not in_registry and not in_alias:
            missing.append(db_name)

    assert not missing, (
        f"Supplier(s) in DB not covered by registry or aliases: {missing}"
    )
    assert len(db_names) == 40, f"Expected 40 DB rows, got {len(db_names)}"
    print(
        f"_selftest passed: {len(SUPPLIER_ACCESS)} registry entries, "
        f"{len(ALIASES)} aliases, {len(db_names)} DB rows all covered."
    )


if __name__ == "__main__":
    _selftest()
