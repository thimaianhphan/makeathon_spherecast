"""
Raw Material Compliance Checker — BOM + Supplier Website Enrichment

What this script does:
1. Connects to the SQLite database.
2. Loads raw-material BOM components for one finished product.
3. Normalizes raw-material SKU names into readable ingredient names.
4. Loads suppliers linked to each raw material from the database.
5. Checks whether each supplier is in the official supplier allowlist.
6. Scrapes ONLY the allowlisted supplier websites.
7. Extracts explicit evidence terms from those supplier pages.
8. Matches simple regulation references based on detected terms.
9. Returns a raw-material assessment focused on:
   - supplier match
   - supplier allowlist status
   - supplier evidence
   - regulation references
   - raw-material evidence status

Important:
- This version checks raw materials only.
- It does NOT validate the final finished product yet.
- It does NOT search the open web.
- It uses only the supplier URLs defined in compliance_config.py.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, List
from urllib.parse import urlparse

from compliance_config import (
    ALLOWED_SUPPLIER_URLS,
    ALLOWED_DOMAINS,
    USER_AGENT,
    SUPPLIER_ALLOWLIST,
    OFFICIAL_REGULATIONS,
    WEBSITE_EVIDENCE_KEYWORDS,
    ALLERGEN_TERMS,
    HAZARD_TERMS,
)

import requests
from bs4 import BeautifulSoup

from compliance_config import (
    ALLOWED_SUPPLIER_URLS,
    ALLOWED_DOMAINS,
    USER_AGENT,
    SUPPLIER_ALLOWLIST,
    OFFICIAL_REGULATIONS,
    WEBSITE_EVIDENCE_KEYWORDS,
    ALLERGEN_TERMS,
    HAZARD_TERMS,
)

DB_PATH = r"data\db.sqlite"
TARGET_FINISHED_PRODUCT_ID = 14
REQUEST_TIMEOUT_SECONDS = 20


@dataclass
class SupplierInfo:
    supplier_id: int
    supplier_name: str


@dataclass
class SupplierCheckResult:
    supplier_id: int
    supplier_name: str
    supplier_match_status: str
    official_website_known: bool
    official_domain: str | None
    official_url: str | None
    message: str


@dataclass
class RawMaterial:
    ingredient_id: int
    ingredient_sku: str
    normalized_name: str
    suppliers: List[SupplierInfo]


@dataclass
class ExternalEvidence:
    source_url: str
    source_domain: str
    ingredient_name_match: bool
    matched_terms: List[str]
    matched_snippets: List[str]
    confidence: str


@dataclass
class RegulationReference:
    rule_id: str
    title: str
    source_url: str
    matched_reason: str
    text: str


@dataclass
class RawMaterialAssessment:
    ingredient_id: int
    ingredient_sku: str
    normalized_name: str
    suppliers: List[SupplierInfo]
    supplier_checks: List[SupplierCheckResult]
    external_evidence: List[ExternalEvidence]
    regulation_references: List[RegulationReference]
    status: str
    rationale: List[str]


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_raw_materials_for_finished_product(
    conn: sqlite3.Connection,
    finished_product_id: int
) -> List[sqlite3.Row]:
    query = """
    SELECT
        bc.ConsumedProductId AS IngredientId,
        p_component.SKU AS IngredientSKU
    FROM BOM b
    JOIN BOM_Component bc
        ON b.Id = bc.BOMId
    JOIN Product p_component
        ON bc.ConsumedProductId = p_component.Id
    WHERE b.ProducedProductId = ?
    ORDER BY bc.ConsumedProductId
    """
    return conn.execute(query, (finished_product_id,)).fetchall()


def fetch_suppliers_for_ingredient(
    conn: sqlite3.Connection,
    ingredient_id: int
) -> List[SupplierInfo]:
    query = """
    SELECT
        s.Id AS SupplierId,
        s.Name AS SupplierName
    FROM Supplier_Product sp
    JOIN Supplier s
        ON sp.SupplierId = s.Id
    WHERE sp.ProductId = ?
    ORDER BY s.Name
    """
    rows = conn.execute(query, (ingredient_id,)).fetchall()

    return [
        SupplierInfo(
            supplier_id=row["SupplierId"],
            supplier_name=row["SupplierName"],
        )
        for row in rows
    ]


def normalize_ingredient_name(raw_sku: str) -> str:
    if not raw_sku:
        return ""

    text = raw_sku.lower().strip()
    text = re.sub(r"^rm-[a-z0-9]+-", "", text)
    text = re.sub(r"-[a-f0-9]{6,}$", "", text)
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in ALLOWED_DOMAINS and url in ALLOWED_SUPPLIER_URLS


def fetch_page_text(url: str) -> str:
    if not is_allowed_url(url):
        raise ValueError(f"URL not allowlisted: {url}")

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def extract_snippets(text: str, search_terms: List[str], window: int = 80) -> List[str]:
    snippets: List[str] = []
    lowered = text.lower()

    for term in search_terms:
        term = term.lower().strip()
        if not term:
            continue

        for match in re.finditer(re.escape(term), lowered):
            start = max(0, match.start() - window)
            end = min(len(lowered), match.end() + window)
            snippet = lowered[start:end].strip()

            if snippet not in snippets:
                snippets.append(snippet)

            if len(snippets) >= 5:
                return snippets

    return snippets


def build_search_terms(normalized_name: str) -> List[str]:
    terms = [normalized_name]
    terms.extend([t for t in normalized_name.split() if len(t) > 2])

    seen = set()
    deduped = []
    for term in terms:
        if term not in seen:
            deduped.append(term)
            seen.add(term)

    return deduped


def normalize_supplier_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def check_suppliers_against_allowlist(suppliers: List[SupplierInfo]) -> List[SupplierCheckResult]:
    normalized_allowlist = {
        normalize_supplier_name(name): data
        for name, data in SUPPLIER_ALLOWLIST.items()
    }

    results: List[SupplierCheckResult] = []

    for supplier in suppliers:
        normalized_name = normalize_supplier_name(supplier.supplier_name)
        match = normalized_allowlist.get(normalized_name)

        if match:
            results.append(
                SupplierCheckResult(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    supplier_match_status="MATCHED_ALLOWLIST",
                    official_website_known=True,
                    official_domain=match["official_domain"],
                    official_url=match["official_url"],
                    message="Supplier official website is in our allowlist.",
                )
            )
        else:
            results.append(
                SupplierCheckResult(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    supplier_match_status="NOT_IN_ALLOWLIST",
                    official_website_known=False,
                    official_domain=None,
                    official_url=None,
                    message="This supplier's official website is not yet in our list.",
                )
            )

    return results


def extract_external_evidence_for_material(
    normalized_name: str,
    page_text_by_url: Dict[str, str]
) -> List[ExternalEvidence]:
    search_terms = build_search_terms(normalized_name)
    results: List[ExternalEvidence] = []

    support_terms: List[str] = []
    for values in WEBSITE_EVIDENCE_KEYWORDS.values():
        support_terms.extend(values)

    for url, text in page_text_by_url.items():
        ingredient_name_match = any(term in text for term in search_terms)
        matched_terms = [term for term in support_terms if term in text]

        if ingredient_name_match:
            snippets = extract_snippets(text, search_terms + matched_terms[:5])

            confidence = "medium"
            if ingredient_name_match and matched_terms:
                confidence = "high"

            results.append(
                ExternalEvidence(
                    source_url=url,
                    source_domain=urlparse(url).netloc,
                    ingredient_name_match=True,
                    matched_terms=matched_terms[:15],
                    matched_snippets=snippets,
                    confidence=confidence,
                )
            )

    return results


def match_regulations(
    normalized_name: str,
    external_evidence: List[ExternalEvidence]
) -> List[RegulationReference]:
    matched: List[RegulationReference] = []

    all_terms = set(normalized_name.split())
    for evidence in external_evidence:
        all_terms.update(evidence.matched_terms)

    if any(term in all_terms for term in ALLERGEN_TERMS):
        rule = OFFICIAL_REGULATIONS[0]
        matched.append(
            RegulationReference(
                rule_id=rule["rule_id"],
                title=rule["title"],
                source_url=rule["source_url"],
                matched_reason="Possible allergen-relevant raw material detected.",
                text=rule["text"],
            )
        )

    if any(term in all_terms for term in HAZARD_TERMS):
        rule = OFFICIAL_REGULATIONS[1]
        matched.append(
            RegulationReference(
                rule_id=rule["rule_id"],
                title=rule["title"],
                source_url=rule["source_url"],
                matched_reason="Possible safety / hazard-control relevance detected.",
                text=rule["text"],
            )
        )

    return matched


def assess_raw_material(
    raw_material: RawMaterial,
    page_text_by_url: Dict[str, str]
) -> RawMaterialAssessment:
    supplier_checks = check_suppliers_against_allowlist(raw_material.suppliers)
    external = extract_external_evidence_for_material(raw_material.normalized_name, page_text_by_url)
    regulations = match_regulations(raw_material.normalized_name, external)

    rationale: List[str] = []

    if raw_material.suppliers:
        rationale.append(f"Found {len(raw_material.suppliers)} supplier(s) linked to this raw material in the database.")
    else:
        rationale.append("No suppliers are linked to this raw material in the database.")

    matched_supplier_count = sum(1 for check in supplier_checks if check.official_website_known)
    if matched_supplier_count > 0:
        rationale.append(f"{matched_supplier_count} supplier(s) matched the official supplier allowlist.")
    else:
        rationale.append("No linked supplier matched the official supplier allowlist.")

    if external:
        rationale.append(f"Found supplier-site evidence on {len(external)} allowlisted page(s).")
    else:
        rationale.append("No supplier-site evidence found on the allowlisted pages.")

    if regulations:
        rationale.append(f"Matched {len(regulations)} regulation reference(s) for this raw material.")
    else:
        rationale.append("No regulation reference was triggered by the current evidence.")

    if external and any(ev.confidence == "high" for ev in external):
        status = "VALID_RAW_MATERIAL"
        rationale.append("Supplier-site evidence is strong enough for an initial raw-material assessment.")
    elif external or matched_supplier_count > 0:
        status = "RISKY_RAW_MATERIAL"
        rationale.append("Some support exists, but evidence is still limited.")
    else:
        status = "INSUFFICIENT_EVIDENCE"
        rationale.append("The allowlisted supplier pages do not provide enough support for this raw material.")

    return RawMaterialAssessment(
        ingredient_id=raw_material.ingredient_id,
        ingredient_sku=raw_material.ingredient_sku,
        normalized_name=raw_material.normalized_name,
        suppliers=raw_material.suppliers,
        supplier_checks=supplier_checks,
        external_evidence=external,
        regulation_references=regulations,
        status=status,
        rationale=rationale,
    )


def load_allowlisted_supplier_pages() -> Dict[str, str]:
    page_text_by_url: Dict[str, str] = {}

    for url in ALLOWED_SUPPLIER_URLS:
        try:
            page_text_by_url[url] = fetch_page_text(url)
        except Exception as exc:
            page_text_by_url[url] = f"__FETCH_ERROR__: {exc}"

    return page_text_by_url


def run_raw_material_checker(
    db_path: str,
    finished_product_id: int
) -> List[RawMaterialAssessment]:
    conn = get_connection(db_path)
    try:
        rows = fetch_raw_materials_for_finished_product(conn, finished_product_id)
        if not rows:
            raise ValueError(f"No BOM components found for finished product id {finished_product_id}")

        raw_materials = []
        for row in rows:
            ingredient_id = row["IngredientId"]
            suppliers = fetch_suppliers_for_ingredient(conn, ingredient_id)

            raw_materials.append(
                RawMaterial(
                    ingredient_id=ingredient_id,
                    ingredient_sku=row["IngredientSKU"],
                    normalized_name=normalize_ingredient_name(row["IngredientSKU"]),
                    suppliers=suppliers,
                )
            )
    finally:
        conn.close()

    raw_page_text_by_url = load_allowlisted_supplier_pages()

    page_text_by_url = {
        url: text for url, text in raw_page_text_by_url.items()
        if not text.startswith("__FETCH_ERROR__:")
    }

    return [
        assess_raw_material(raw_material=rm, page_text_by_url=page_text_by_url)
        for rm in raw_materials
    ]


def assessments_to_json(assessments: List[RawMaterialAssessment]) -> str:
    payload = {
        "raw_material_count": len(assessments),
        "results": [asdict(a) for a in assessments],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    assessments = run_raw_material_checker(
        db_path=DB_PATH,
        finished_product_id=TARGET_FINISHED_PRODUCT_ID,
    )
    print(assessments_to_json(assessments))