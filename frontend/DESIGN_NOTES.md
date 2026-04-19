# Agnes Frontend Redesign Notes

## Layout Rationale

The main analysis screen is intentionally split into three persistent regions on desktop:

- Left rail: finished-good summary plus clickable ingredient list.
- Center pane: top 3 variant cards for the currently selected raw material.
- Right rail: full evidence trail for the currently hovered or selected variant.

This keeps decision context stable. Analysts can compare alternatives in the center while immediately verifying source provenance in the right rail without modal hops.

On mobile, the same model is preserved using tabs (`Ingredients`, `Variants`, `Evidence`) so all information remains available without shrinking readability.

## Scoring Formula

Displayed formula in UI:

`Composite = 0.5 x Compliance + 0.3 x Quality + 0.2 x Price`

Why:

- Compliance is highest weight because regulatory safety is a hard gate.
- Quality is second because functional equivalence must remain acceptable.
- Price is optimization on top and should not overpower safety/fitness.

Price unknown values remain neutral (`50`) and are explicitly labeled as unverified.

Variant ordering uses the composite score first, with tie-breakers in this order:

- Compliance
- Quality
- Price

This preserves the intended priority: compliance > quality > price.

## Backend Compatibility Notes

Current backend behavior is compatibility mode:

- `POST /api/sourcing/analyze/:id` returns a full analysis payload synchronously.
- `GET /api/sourcing/analyze/:id/status` is not available yet.
- SSE uses the generic stream endpoint (`/api/stream`) and is used only for live progress text.

The frontend API client adapts this payload into the `FinishedGoodAnalysis` shape used by the new UI.

## Evidence-First Philosophy

The UI is designed for trust and auditability, not just rankings:

- Every variant card exposes evidence chips directly.
- Clicking a chip focuses the matching source in the evidence panel.
- Evidence entries show the backend-provided excerpt verbatim, the raw URL, confidence, support category, and fetch time.
- LLM-only/no-evidence items are visually muted and confidence is capped in presentation.

The goal is to let users validate *why* a recommendation exists, not just accept a score.
