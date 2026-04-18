"""
Regulatory References — Agnes AI Supply Chain Manager.

Curated citation map for EU food regulations and common additives.
No live fetch required — stable EUR-Lex URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.schemas import EvidenceItem


@dataclass
class RegulationCitation:
    regulation_id: str
    title: str
    url: str
    summary: str


# Canonical EU food regulation citations
EU_REGULATIONS: dict[str, RegulationCitation] = {
    "EU 1169/2011": RegulationCitation(
        regulation_id="EU 1169/2011",
        title="Regulation (EU) No 1169/2011 — Food Information to Consumers (FIC)",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011R1169",
        summary="Mandates declaration of 14 major allergens on food labels. Allergens must be emphasized when present as ingredients.",
    ),
    "EU 1333/2008": RegulationCitation(
        regulation_id="EU 1333/2008",
        title="Regulation (EC) No 1333/2008 — Food Additives",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32008R1333",
        summary="Establishes approved food additives (E-numbers) per food category. Unapproved additives are prohibited.",
    ),
    "EU 834/2007": RegulationCitation(
        regulation_id="EU 834/2007",
        title="Council Regulation (EC) No 834/2007 — Organic Production",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32007R0834",
        summary="Superseded by EU 2018/848. Defined organic production rules; synthetic additives generally prohibited.",
    ),
    "EU 2018/848": RegulationCitation(
        regulation_id="EU 2018/848",
        title="Regulation (EU) 2018/848 — Organic Production (current)",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32018R0848",
        summary="Current EU organic regulation replacing EC 834/2007. Restricts non-organic ingredients to ≤5% in organic products.",
    ),
    "EU 1829/2003": RegulationCitation(
        regulation_id="EU 1829/2003",
        title="Regulation (EC) No 1829/2003 — Genetically Modified Food and Feed",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32003R1829",
        summary="GMO ingredients >0.9% must be labelled. Pre-market authorisation required for new GM foods.",
    ),
    "EU 1924/2006": RegulationCitation(
        regulation_id="EU 1924/2006",
        title="Regulation (EC) No 1924/2006 — Nutrition and Health Claims",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32006R1924",
        summary="Regulates nutrition and health claims on food. Claims must be scientifically justified and authorised.",
    ),
}

# Curated E-number → EFSA opinion / EUR-Lex additive info
ADDITIVE_CITATIONS: dict[str, dict] = {
    "E322": {"name": "Lecithin", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4650",
             "note": "EFSA 2017: lecithins re-evaluated, safe at current uses."},
    "E471": {"name": "Mono- and diglycerides of fatty acids",
             "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4786",
             "note": "EFSA 2017: acceptable daily intake not specified; safe at current use levels."},
    "E415": {"name": "Xanthan Gum", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4909",
             "note": "EFSA 2017: xanthan gum re-evaluated, no safety concern at reported uses."},
    "E412": {"name": "Guar Gum", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4669",
             "note": "EFSA 2017: guar gum acceptable; high doses may affect nutrient absorption."},
    "E440": {"name": "Pectin", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4866",
             "note": "EFSA 2017: pectins re-evaluated, no safety concern."},
    "E300": {"name": "Ascorbic acid (Vitamin C)",
             "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4289",
             "note": "EFSA 2015: ascorbic acid and ascorbates, acceptable daily intake not specified."},
    "E330": {"name": "Citric acid", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4353",
             "note": "EFSA 2014: citric acid and citrates, no safety concern at current uses."},
    "E202": {"name": "Potassium sorbate", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/3454",
             "note": "EFSA 2015: sorbic acid and sorbates, group ADI 25 mg/kg bw/day."},
    "E211": {"name": "Sodium benzoate", "url": "https://www.efsa.europa.eu/en/efsajournal/pub/3316",
             "note": "EFSA 2016: benzoic acid and benzoates, group ADI 5 mg/kg bw/day."},
    "E621": {"name": "Monosodium glutamate (MSG)",
             "url": "https://www.efsa.europa.eu/en/efsajournal/pub/4910",
             "note": "EFSA 2017: glutamic acid and glutamates re-evaluated, ADI 30 mg/kg bw/day."},
}


def get_regulation_evidence(regulation_id: str, claim: Optional[str] = None) -> Optional[EvidenceItem]:
    """Return a regulatory_reference EvidenceItem for a given regulation ID."""
    reg = EU_REGULATIONS.get(regulation_id)
    if not reg:
        return None
    from datetime import datetime
    return EvidenceItem(
        source_type="regulatory_reference",
        source_url=reg.url,
        source_title=reg.title,
        excerpt=reg.summary,
        confidence=0.95,
        timestamp=datetime.utcnow().isoformat() + "Z",
        claim=claim or f"Regulatory basis: {regulation_id}",
    )


def get_additive_evidence(e_number: str, claim: Optional[str] = None) -> Optional[EvidenceItem]:
    """Return an EvidenceItem for a specific E-number from the curated EFSA map."""
    key = e_number.upper()
    entry = ADDITIVE_CITATIONS.get(key)
    if not entry:
        return None
    from datetime import datetime
    return EvidenceItem(
        source_type="regulatory_reference",
        source_url=entry["url"],
        source_title=f"EFSA opinion on {entry['name']} ({key})",
        excerpt=entry["note"],
        confidence=0.92,
        timestamp=datetime.utcnow().isoformat() + "Z",
        claim=claim or f"EU approval status of {key}",
    )


def list_regulation_ids() -> list[str]:
    return list(EU_REGULATIONS.keys())
