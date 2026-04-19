import html
import os
import re
import time

from google import genai
from google.api_core.exceptions import ResourceExhausted

GEMINI_MODEL = "gemini-2.5-flash"

QUALITY_SCORES = {
    "pharmaceutical grade": 1.0,
    "usp":                  1.0,
    "ep":                   1.0,
    "bp":                   1.0,
    "gmp":                  0.9,
    "food grade":           0.7,
    "kosher":               0.7,
    "halal":                0.7,
    "organic":              0.7,
    "feed grade":           0.4,
    "industrial grade":     0.2,
}

COMPLIANCE_METRICS = {
    "identity_confidence": "match to reference (chromatographic/spectral/DNA) ∈ (0,1)",
    "assay_potency":       "active content vs spec (ratio to label claim), target ~1.0",
    "heavy_metals":        "Pb, Cd, As, Hg aggregate in ppm",
    "pesticide_residues":  "multi-residue levels in ppb/ppm (esp. botanicals)",
    "microbial_limits":    "1.0 if passes TAMC/TYMC + pathogen absence, 0.0 if fails",
    "moisture_content":    "water content (w/w) ∈ (0,1)",
    "residual_solvents":   "ICH-class solvents in ppm (extracted materials only)",
}

_RETRY_DELAYS = [10, 30, 60, 120]

_nullable_number = {"type": "NUMBER", "nullable": True}
_nullable_string = {"type": "STRING", "nullable": True}

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "prices": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "quantity": _nullable_number,
                    "unit":     _nullable_string,
                    "price":    {"type": "NUMBER"},
                    "currency": {"type": "STRING"},
                },
                "required": ["price", "currency"],
            },
        },
        "purity":  _nullable_number,
        "quality": _nullable_string,
        "compliance": {
            "type": "OBJECT",
            "properties": {k: _nullable_number for k in COMPLIANCE_METRICS},
        },
    },
    "required": ["prices", "compliance"],
}


def _build_prompt(sku: str, page_text: str) -> str:
    metrics_spec = "\n".join(f"- {k}: {v}" for k, v in COMPLIANCE_METRICS.items())
    return f"""Extract structured product data from this supplier page for SKU: {sku}

Extract:
1. All quantity/price tiers (every distinct size and its price). If only "From $X" with no quantity, set quantity and unit to null. currency defaults to USD (EUR for €, GBP for £).
2. Purity as a decimal ∈ [0,1] ("99% pure" → 0.99). null if not stated.
3. Quality grade — pick the highest applicable: "pharmaceutical grade", "usp", "ep", "bp", "gmp", "food grade", "kosher", "halal", "organic", "feed grade", "industrial grade". null if none mentioned.
4. Quality metrics from COA data or product descriptions (null if not found):
{metrics_spec}

Page text:
{page_text[:8000]}"""


def html_to_text(html_content: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_product_info(page_text: str, product_sku: str) -> dict:
    """
    Calls Gemini to extract pricing and quality attributes from a supplier page.

    Returns:
        prices:          list of {quantity: float|None, unit: str|None, price: float, currency: str}
        purity:          float ∈ [0,1] or None
        quality:         str label or None
        quality_score:   float ∈ [0,1] from QUALITY_SCORES, or None
        compliance: {k: float|None for k in COMPLIANCE_METRICS}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(product_sku, page_text)

    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            print(f"    rate limited, retrying in {delay}s...")
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": _RESPONSE_SCHEMA,
                },
            )
            break
        except ResourceExhausted:
            if attempt == len(_RETRY_DELAYS):
                raise

    result = response.parsed or {}

    purity = result.get("purity")
    result["purity"] = purity / 100 if purity is not None and purity > 1 else purity

    quality_label = (result.get("quality") or "").lower().strip()
    result["quality_score"] = QUALITY_SCORES.get(quality_label)

    raw_metrics = result.get("compliance") or {}
    result["compliance"] = {k: raw_metrics.get(k) for k in COMPLIANCE_METRICS}

    return result
