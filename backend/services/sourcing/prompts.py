"""
All LLM prompt templates for the sourcing pipeline in one place.
Weights and thresholds that affect scoring live in subagents/tradeoff.py.
"""

SUPPLIER_EXTRACTION_PROMPT = """You are a data extraction assistant for CPG ingredient sourcing.
Extract structured information from the following webpage content about a supplier or product.
Return ONLY valid JSON with these exact keys (use null for missing values):

{{
  "unit_price_eur": null,
  "currency_original": null,
  "moq": null,
  "lead_time_days": null,
  "claimed_certifications": [],
  "country_of_origin": null,
  "red_flags": []
}}

Rules:
- unit_price_eur: numeric price in EUR; convert if currency shown (null if no price found)
- currency_original: original currency code if not EUR (e.g. "USD", "GBP")
- moq: minimum order quantity as integer (null if not found)
- lead_time_days: lead time in days as integer (null if not found)
- claimed_certifications: list of certification strings (e.g. ["ISO 22000", "Halal", "Kosher"])
- country_of_origin: country name string (null if not found)
- red_flags: list of red flag strings (recalls, sanctions, bankruptcy, quality issues)

Supplier: {supplier_name}
Product: {product_name}
Page URL: {url}
Page content:
{content}"""


JUDGE_REASONING_PROMPT = """You are a CPG procurement expert at Agnes. Write a concise 2-3 sentence
explanation of the sourcing recommendation for the following case.

Original ingredient: {original_name}
Decision: {decision}
Best candidate: {candidate_name} (if any)
Compliance status: {compliance_status}
Evidence sources: {evidence_sources}
Flags: {flags}

Be direct. Cite the key reason for the decision and, for needs_review, state exactly what
the human reviewer must verify. No markdown."""
