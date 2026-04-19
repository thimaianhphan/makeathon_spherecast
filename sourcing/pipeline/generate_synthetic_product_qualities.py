"""
Populate synthetic price tiers for every supplier-product pair in the DB.
Each pair gets 1–5 quantity tiers sampled from realistic distributions.
Run from the pipeline/ directory: python generate_synthetic_product_qualities.py
"""
import random
import math
import sys
sys.path.insert(0, ".")
from db import get_supplier_products_enriched, upsert_supplier_product_prices

QUANTITY_TIERS = [1, 5, 10, 25, 50, 100, 500, 1000]  # kg


def _log_normal(mu: float, sigma: float, rng: random.Random) -> float:
    return math.exp(rng.gauss(mu, sigma))


def generate(seed: int = 42, overwrite: bool = False) -> int:
    rng = random.Random(seed)
    pairs = get_supplier_products_enriched()
    count = 0
    for p in pairs:
        # consume rng slots consistently regardless of skipping
        base = round(_log_normal(mu=3.5, sigma=1.0, rng=rng), 4)  # median ~$33/kg
        n_tiers = rng.randint(1, 5)
        tiers = sorted(rng.sample(QUANTITY_TIERS, n_tiers))
        prices = []
        for i, qty in enumerate(tiers):
            discount = rng.uniform(0.05, 0.15) * i
            price = round(base * max(0.4, 1 - discount), 2)
            prices.append({"quantity": float(qty), "unit": "kg", "price": price, "currency": "USD"})

        if not overwrite and p["prices"]:
            continue
        upsert_supplier_product_prices(p["supplier_id"], p["product_id"], prices)
        count += 1
    return count


if __name__ == "__main__":
    n = generate()
    print(f"Generated synthetic prices for {n} supplier-product pairs.")