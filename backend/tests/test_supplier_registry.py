"""
test_supplier_registry.py
=========================
Sanity checks for supplier_registry against the live SQLite DB.
"""
import sqlite3
import pathlib

import pytest

from backend.services.sourcing.supplier_registry import (
    ALIASES,
    SUPPLIER_ACCESS,
    _selftest,
    get_access,
    is_opaque,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "db.sqlite"


def _db_names() -> list[str]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT Name FROM Supplier ORDER BY Id").fetchall()
    con.close()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_db_has_40_suppliers():
    names = _db_names()
    assert len(names) == 40, f"Expected 40 suppliers in DB, got {len(names)}"


def test_selftest_passes():
    """_selftest() must not raise for any DB supplier name."""
    _selftest()


def test_all_db_suppliers_covered():
    """Every supplier name from the DB resolves to a non-None access record."""
    covered = set(SUPPLIER_ACCESS.keys()) | set(ALIASES.values())
    alias_keys = set(ALIASES.keys())
    missing = []
    for name in _db_names():
        if name not in covered and name.lower() not in alias_keys:
            missing.append(name)
    assert not missing, f"DB suppliers not covered by registry: {missing}"


def test_registry_has_40_entries():
    assert len(SUPPLIER_ACCESS) == 40, (
        f"Expected 40 entries in SUPPLIER_ACCESS, got {len(SUPPLIER_ACCESS)}"
    )


def test_tier_values_are_valid():
    valid_tiers = {"full", "full_3p", "spec_only", "opaque"}
    for name, info in SUPPLIER_ACCESS.items():
        assert info["tier"] in valid_tiers, (
            f"{name!r} has invalid tier {info['tier']!r}"
        )


def test_full_suppliers_have_base_url_and_search_pattern():
    for name, info in SUPPLIER_ACCESS.items():
        if info["tier"] in ("full", "full_3p"):
            assert info["base_url"] is not None, (
                f"{name!r} (tier={info['tier']}) must have base_url"
            )
            assert info["search_pattern"] is not None, (
                f"{name!r} (tier={info['tier']}) must have search_pattern"
            )
            assert "{material}" in info["search_pattern"], (
                f"{name!r} search_pattern must contain {{material}} placeholder"
            )


def test_opaque_suppliers_return_true():
    opaque_names = [
        "ADM", "Actus Nutrition", "Cambrex", "Cargill",
        "Gold Coast Ingredients", "Makers Nutrition",
        "Sawgrass Nutra Labs", "Sensient", "Virginia Dare", "Vitaquest",
    ]
    for name in opaque_names:
        assert is_opaque(name), f"is_opaque({name!r}) should be True"


def test_full_suppliers_return_false_for_is_opaque():
    full_names = [
        "BulkSupplements", "Capsuline", "Custom Probiotics",
        "Nutri Avenue", "PureBulk", "Source-Omega LLC",
        "Spectrum Chemical", "Trace Minerals",
    ]
    for name in full_names:
        assert not is_opaque(name), f"is_opaque({name!r}) should be False"


def test_get_access_case_insensitive():
    assert get_access("bulksupplements") is not None
    assert get_access("PUREBULK") is not None
    assert get_access("adm") is not None


def test_get_access_whitespace_trimmed():
    assert get_access("  PureBulk  ") is not None
    assert get_access("  ADM  ") is not None


def test_get_access_unknown_returns_none():
    assert get_access("NonExistentSupplierXYZ") is None
    assert get_access("") is None


def test_is_opaque_unknown_supplier():
    assert is_opaque("SomeRandomUnknownCo") is True
