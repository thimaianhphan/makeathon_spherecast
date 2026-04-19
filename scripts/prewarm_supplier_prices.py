"""
prewarm_supplier_prices.py
==========================
CLI script that iterates every Supplier_Product mapping in the DB and
populates Supplier_Price_Cache by invoking the same scraper used at
request time.

Goal: a demo-able "pre-scrape once, serve instantly" path so that the
first /api/sourcing/analyze call for a known BOM responds instantly.

Usage
-----
    python -m scripts.prewarm_supplier_prices [OPTIONS]

Options
-------
  --stats                  Print cache coverage stats and exit.
  --dry-run                Log what would be scraped; no network / DB writes.
  --only-tier {full,full_3p,spec_only}
                           Restrict to suppliers with this tier only.
                           Default: all non-opaque tiers.
  --concurrency N          asyncio.Semaphore width for concurrent scrapes.
                           Default: 8.
  --ttl-hours H            Skip pairs already cached within H hours.
                           Default: config.SUPPLIER_PRICE_CACHE_TTL_HOURS (168).
"""

from __future__ import annotations

import asyncio
import argparse
import json
import time

from backend.services import db_service
from backend.services.sourcing import supplier_registry, price_cache
from backend.services.sourcing.subagents.supplier_scout import _scout_one
from backend.services.sourcing.sku_utils import material_name_from_sku
from backend.config import SUPPLIER_PRICE_CACHE_TTL_HOURS


async def main(args: argparse.Namespace) -> None:
    db_service.ensure_price_cache_table()

    # ── --stats mode: print cache coverage and exit ───────────────────────────
    if args.stats:
        print(json.dumps(price_cache.stats(), indent=2))
        return

    # ── Load all Supplier_Product mappings ────────────────────────────────────
    mappings = db_service.get_supplier_product_mappings()

    def keep(row: dict) -> bool:
        access = supplier_registry.get_access(row["supplier_name"])
        if not access or access["tier"] == "opaque":
            return False
        if args.only_tier and access["tier"] != args.only_tier:
            return False
        return True

    todo = [m for m in mappings if keep(m)]

    # ── Skip pairs already fresh in the cache ────────────────────────────────
    ttl = args.ttl_hours if args.ttl_hours is not None else SUPPLIER_PRICE_CACHE_TTL_HOURS
    pairs = [(m["supplier_id"], m["product_id"]) for m in todo]
    fresh = price_cache.get_many(pairs, ttl_hours=ttl)
    skipped_fresh = len(fresh)
    todo = [m for m in todo if (m["supplier_id"], m["product_id"]) not in fresh]

    # ── Concurrency control ───────────────────────────────────────────────────
    sem = asyncio.Semaphore(args.concurrency)
    done: dict[str, int] = {"ok": 0, "err": 0, "dry": 0}

    async def worker(row: dict) -> None:
        async with sem:
            candidate = {
                "Id": row["product_id"],
                "SKU": row["product_sku"],
                "Name": row["product_name"],
            }

            if args.dry_run:
                material = material_name_from_sku(row["product_sku"])
                access = supplier_registry.get_access(row["supplier_name"])
                tier = access["tier"] if access else "unknown"
                print(f"[dry] supplier={row['supplier_name']!r:40s} "
                      f"tier={tier:10s} material={material!r}")
                done["dry"] += 1
                return

            try:
                ev = await _scout_one(row["supplier_id"], row["supplier_name"], candidate)
                if ev.source_type != "no_evidence":
                    price_cache.put(
                        ev,
                        product_id=row["product_id"],
                        material_name=material_name_from_sku(row["product_sku"]),
                    )
                print(
                    f"[ok]  {row['supplier_name']!r} :: {row['product_sku']} "
                    f"→ price={ev.unit_price_eur} src={ev.source_type}"
                )
                done["ok"] += 1
            except Exception as exc:
                print(
                    f"[err] {row['supplier_name']!r} :: {row['product_sku']} "
                    f"→ {exc!r}"
                )
                done["err"] += 1

    # ── Run ───────────────────────────────────────────────────────────────────
    excluded_total = len(mappings) - len([m for m in mappings if keep(m)]) - skipped_fresh
    print(
        f"Warming {len(todo)} pairs  "
        f"(skipped {skipped_fresh} already-fresh, "
        f"excluded opaque/wrong-tier: {excluded_total})…"
    )

    start = time.time()
    try:
        await asyncio.gather(*(worker(r) for r in todo))
    except KeyboardInterrupt:
        print("\nInterrupted. Cache rows committed so far are safe.")

    elapsed = time.time() - start
    print(
        f"\nSummary: warmed={done['ok']} errors={done['err']} "
        f"dry={done['dry']} total_pairs_considered={len(todo)} "
        f"elapsed={elapsed:.1f}s"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pre-warm the Supplier_Price_Cache for all Supplier_Product mappings."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="asyncio.Semaphore width (default: 8).",
    )
    parser.add_argument(
        "--only-tier",
        choices=["full", "full_3p", "spec_only"],
        default=None,
        help="Restrict to suppliers with this access tier only.",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=None,
        help=(
            "Skip pairs already cached within this many hours "
            f"(default: SUPPLIER_PRICE_CACHE_TTL_HOURS={SUPPLIER_PRICE_CACHE_TTL_HOURS})."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be scraped without performing any network calls or writes.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print cache coverage statistics and exit.",
    )

    args = parser.parse_args()
    asyncio.run(main(args))
