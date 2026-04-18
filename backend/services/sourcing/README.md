# Agnes Sourcing Pipeline

Sub-agent pipeline that proposes cheaper, compliant supplier alternatives for each raw material in a finished good's BOM.

## Flow

```
POST /api/sourcing/analyze/{finished_good_id}
         │
         ▼
  SourcingOrchestrator.run()
         │  loads BOM, raw-materials catalog, supplier mappings once
         │
         ▼  asyncio.gather — one pipeline per BOM component
  ┌──────────────────────────────────────────────────┐
  │             RawMaterialPipeline                  │
  │                                                  │
  │  1. Equivalence agent   (LLM classification)     │
  │  2. Supplier Scout      (DB + web search/fetch)  │
  │  3. Compliance agent    (LLM + evidence)         │
  │  4. Tradeoff agent      (pure Python scoring)    │
  │  5. Judge               (gate + LLM reasoning)   │
  └──────────────────────────────────────────────────┘
         │
         ▼
  SourcingProposal  (structured JSON)
```

Each stage runs **sequentially** inside a pipeline (each depends on the prior). Pipelines for different raw materials run **in parallel**.

## Evidence Trust Hierarchy

From highest to lowest trust (encoded in the Judge):

1. **Regulatory / certification DB confirmations** — `source="database"`
2. **Supplier official website / spec sheet** — `source_type="supplier_site"`, `source="enriched"`
3. **Reputable news / trade publications** — `source_type="news"`, `source="enriched"`
4. **LLM inference without external support** — `source="inferred"`, confidence capped at 0.6

When evidence conflicts, higher-tier wins. When tiers tie, prefer the more recent source.

A `judge_decision="accept"` is only emitted when:
- All compliance checks have confidence ≥ 0.8
- At least one compliance check is backed by `source="enriched"` or `source="database"` (not pure LLM)
- No supplier red flags
- No marginal savings (<2%)

## Tuning Tradeoff Weights

Edit `TRADEOFF_WEIGHTS` in [subagents/tradeoff.py](subagents/tradeoff.py):

```python
TRADEOFF_WEIGHTS: dict[str, float] = {
    "cost": 0.35,             # price evidence from web
    "lead_time": 0.20,        # lead-time days from supplier pages
    "single_source_risk": 0.20,  # penalise single-supplier candidates
    "compliance_confidence": 0.15,  # avg compliance check confidence
    "consolidation": 0.10,    # bonus if candidate appears in multiple BOMs
}
```

Weights must sum to 1.0. No restart required — changes take effect on the next API call.

## Key Design Constraints

- **No fabricated URLs or prices.** If web search returns nothing, `source_type="no_evidence"` and `confidence=0`.
- **No DB writes from sub-agents.** Only the orchestrator layer aggregates; sub-agents return data.
- **Graceful degradation.** A Scout failure for one candidate continues the pipeline; the Judge marks `needs_review`.
- **Cache scope.** `sourcing/cache.py` is reset per orchestrator run (not persisted). File-based classification cache (`data/rm_classification.json`) persists across runs.
