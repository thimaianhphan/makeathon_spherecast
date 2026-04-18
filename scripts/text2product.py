import html
import json
import os
import re
import time

from google import genai
from google.api_core.exceptions import ResourceExhausted

GEMINI_MODEL = "gemini-2.5-flash"
_QUALITY_SCORES = {
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

QUALITY_METRICS = {
    "identity_confidence": "match to reference (chromatographic/spectral/DNA) ∈ (0,1)",
    "assay_potency": "active content vs spec (ratio to label claim), target ~1.0",
    "heavy_metals": "Pb, Cd, As, Hg each in ppm (must meet limits)",
    "pesticide_residues": "multi-residue levels in ppb/ppm (must meet limits; esp. botanicals)",
    "microbial_limits": "TAMC/TYMC (CFU/g) + absence of pathogens (Salmonella, E. coli)",
    "moisture_content": "water content (w/w) ∈ (0,1) or % (impacts stability)",
    "residual_solvents": "ICH-class solvents in ppm (if extracted materials)"
}

_RETRY_DELAYS = [10, 30, 60, 120]

_PROMPT_TEMPLATE = "\n".join([
    "You are extracting structured product data from a supplier website page.",
    "Product SKU: {sku}",
    "",
    "Extract from the page text:",
    "1. All available quantity/price tiers (e.g. 100g for $5.00, 500g for $20.00). Include every distinct tier.",
    "2. Purity as a decimal fraction ∈ [0,1] if stated (e.g. \"99% pure\" → 0.99, \">98%\" → 0.98). null if not stated.",
    "3. Quality grade or certification. Map to one of these exact labels (pick the highest that applies):",
    "   \"pharmaceutical grade\", \"usp\", \"ep\", \"bp\", \"gmp\", \"food grade\", \"kosher\", \"halal\", \"organic\",",
    "   \"feed grade\", \"industrial grade\" — or null if none mentioned.",
    "4. Quality metrics from COA data or product descriptions if present. All fields are null if not stated:",
    *[f"   - {k}: {v}" for k, v in QUALITY_METRICS.items()],
    "",
    "Return ONLY valid JSON matching exactly this schema:",
    "{{",
    "  \"prices\": [",
    "    {{\"quantity\": <number or null>, \"unit\": \"<unit string or null>\", \"price\": <number>, \"currency\": \"<3-letter ISO code>\"}}",
    "  ],",
    "  \"purity\": <decimal fraction 0–1 or null>,",
    "  \"quality\": \"<quality label or null>\",",
    "  \"quality_metrics\": {{",
    *[f"    \"{k}\": <number or null>," for k in QUALITY_METRICS],
    "  }}",
    "}}",
    "",
    "Rules:",
    "- If a price is listed as \"From $X\" with no specific quantity, set quantity and unit to null.",
    "- currency is \"USD\" unless the page clearly shows a different currency symbol (EUR for €, GBP for £).",
    "- If no price information is found, return an empty prices array.",
    "",
    "Page text:",
    "{text}",
])


def html_to_text(html_content: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_product_info(page_text: str, product_sku: str) -> dict:
    """
    Calls Gemini to extract quantity/price tiers, purity, and quality from supplier page text.

    Returns:
        {
          "prices": [{"quantity": float|None, "unit": str|None, "price": float, "currency": str}],
          "purity": str|None,
          "quality": str|None,
        }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)
    prompt = _PROMPT_TEMPLATE.format(sku=product_sku, text=page_text[:8000])

    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            print(f"    rate limited, retrying in {delay}s...")
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            break
        except ResourceExhausted:
            if attempt == len(_RETRY_DELAYS):
                raise

    result = json.loads(response.text)
    quality_label = (result.get("quality") or "").lower().strip()
    result["quality_score"] = _QUALITY_SCORES.get(quality_label)
    raw_metrics = result.get("quality_metrics") or {}
    result["quality_metrics"] = {k: raw_metrics.get(k) for k in QUALITY_METRICS}
    purity = result.get("purity")
    if purity is not None:
        result["purity"] = purity / 100 if purity > 1 else purity
    return result

