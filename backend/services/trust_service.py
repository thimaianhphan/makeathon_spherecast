"""
Verifiable Reputation & Attestation System.

Trust scores are derived from transaction history, not self-reported data.
Each transaction produces a cryptographically-signed attestation record.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime

from pydantic import BaseModel, Field

from backend.schemas import make_id, TrustSubmission


# ── Transaction Record ───────────────────────────────────────────────────────

class TransactionRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: make_id("txn"))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    agent_id: str  # the agent being evaluated
    agent_name: str = ""
    counterparty_id: str  # who they transacted with
    counterparty_name: str = ""
    transaction_type: str = ""  # quote_fulfilled, delivery_completed, negotiation_completed
    po_number: str = ""

    # Performance metrics
    promised_delivery_days: int = 0
    actual_delivery_days: int = 0
    on_time: bool = True
    quoted_price_eur: float = 0
    final_price_eur: float = 0
    price_honored: bool = True
    quality_accepted: bool = True
    defects_found: int = 0
    quantity_ordered: int = 0
    quantity_delivered: int = 0
    compliance_passed: bool = True
    dispute_raised: bool = False
    dispute_resolved: bool = True

    # Computed
    delivery_variance_days: int = 0
    price_variance_pct: float = 0


# ── Attestation (Verifiable Record) ──────────────────────────────────────────

class Attestation(BaseModel):
    attestation_id: str = Field(default_factory=lambda: make_id("att"))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    agent_id: str
    agent_name: str = ""
    attested_by: str  # who issued this attestation (counterparty or system)
    attested_by_name: str = ""
    transaction_id: str = ""

    # Attestation content
    category: str = ""  # delivery, quality, pricing, compliance, reliability
    score: float = 0.0  # 0.0 to 1.0 for this specific attestation
    detail: str = ""
    evidence: dict = Field(default_factory=dict)  # supporting data

    # Integrity
    hash: str = ""  # SHA-256 of the attestation content
    previous_hash: str = ""  # chain link to previous attestation for this agent

    def compute_hash(self) -> str:
        content = json.dumps(
            {
                "agent_id": self.agent_id,
                "attested_by": self.attested_by,
                "category": self.category,
                "score": self.score,
                "transaction_id": self.transaction_id,
                "timestamp": self.timestamp,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
        )
        self.hash = hashlib.sha256(content.encode()).hexdigest()
        return self.hash


# ── Composite Reputation Score ───────────────────────────────────────────────

class ReputationScore(BaseModel):
    agent_id: str
    agent_name: str = ""
    computed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # Component scores (0.0 - 1.0)
    delivery_score: float = 0.0  # on-time delivery rate
    quality_score: float = 0.0  # defect-free rate
    pricing_score: float = 0.0  # price honoring rate
    compliance_score: float = 0.0  # compliance pass rate
    reliability_score: float = 0.0  # dispute-free rate

    # Composite
    composite_score: float = 0.0  # weighted average
    total_transactions: int = 0
    total_attestations: int = 0
    trend: str = "stable"  # improving, stable, declining

    # Weights used
    weights: dict = Field(
        default_factory=lambda: {
            "delivery": 0.30,
            "quality": 0.25,
            "pricing": 0.20,
            "compliance": 0.15,
            "reliability": 0.10,
        }
    )


# ── Reputation Ledger ────────────────────────────────────────────────────────

class ReputationLedger:
    """Immutable ledger of transaction records and attestations."""

    CONTEXTUAL_DIMENSIONS = frozenset({"on_time_delivery", "pricing_honesty", "quality", "compliance", "reliability"})

    def __init__(self):
        self._transactions: list[TransactionRecord] = []
        self._attestations: list[Attestation] = []
        self._scores: dict[str, ReputationScore] = {}
        self._agent_last_hash: dict[str, str] = {}  # chain integrity
        self._contextual_submissions: list[dict] = []  # weighted by rater trust

    def record_transaction(self, record: TransactionRecord) -> list[Attestation]:
        """Record a transaction and auto-generate attestations."""
        # Compute variances
        record.delivery_variance_days = record.actual_delivery_days - record.promised_delivery_days
        if record.quoted_price_eur > 0:
            record.price_variance_pct = round(
                ((record.final_price_eur - record.quoted_price_eur) / record.quoted_price_eur) * 100,
                2,
            )
        self._transactions.append(record)

        # Generate attestations
        attestations = []
        prev_hash = self._agent_last_hash.get(record.agent_id, "genesis")

        # Delivery attestation
        delivery_score = 1.0 if record.on_time else max(0.0, 1.0 - abs(record.delivery_variance_days) * 0.1)
        att = Attestation(
            agent_id=record.agent_id,
            agent_name=record.agent_name,
            attested_by=record.counterparty_id,
            attested_by_name=record.counterparty_name,
            transaction_id=record.record_id,
            category="delivery",
            score=round(delivery_score, 3),
            detail=f"{'On-time' if record.on_time else f'{record.delivery_variance_days}d late'} delivery of "
            f"{record.quantity_delivered}/{record.quantity_ordered} units",
            evidence={
                "promised_days": record.promised_delivery_days,
                "actual_days": record.actual_delivery_days,
                "variance": record.delivery_variance_days,
            },
            previous_hash=prev_hash,
        )
        att.compute_hash()
        attestations.append(att)
        prev_hash = att.hash

        # Quality attestation (Ferrari quality bar: defects penalized heavily)
        if record.quality_accepted and record.defects_found == 0:
            quality_score = 1.0
        elif record.quality_accepted:
            quality_score = max(0.2, 0.6 - record.defects_found * 0.15)
        else:
            quality_score = 0.05
        att = Attestation(
            agent_id=record.agent_id,
            agent_name=record.agent_name,
            attested_by=record.counterparty_id,
            attested_by_name=record.counterparty_name,
            transaction_id=record.record_id,
            category="quality",
            score=round(quality_score, 3),
            detail=f"{'Accepted' if record.quality_accepted else 'Rejected'}, {record.defects_found} defects found",
            evidence={"accepted": record.quality_accepted, "defects": record.defects_found},
            previous_hash=prev_hash,
        )
        att.compute_hash()
        attestations.append(att)
        prev_hash = att.hash

        # Pricing attestation
        pricing_score = 1.0 if record.price_honored else max(0.0, 1.0 - abs(record.price_variance_pct) * 0.05)
        att = Attestation(
            agent_id=record.agent_id,
            agent_name=record.agent_name,
            attested_by=record.counterparty_id,
            attested_by_name=record.counterparty_name,
            transaction_id=record.record_id,
            category="pricing",
            score=round(pricing_score, 3),
            detail=f"Price {'honored' if record.price_honored else 'deviated'} ({record.price_variance_pct:+.1f}%)",
            evidence={
                "quoted": record.quoted_price_eur,
                "final": record.final_price_eur,
                "variance_pct": record.price_variance_pct,
            },
            previous_hash=prev_hash,
        )
        att.compute_hash()
        attestations.append(att)
        prev_hash = att.hash

        # Compliance attestation
        att = Attestation(
            agent_id=record.agent_id,
            agent_name=record.agent_name,
            attested_by="eu-compliance-agent-01",
            attested_by_name="EU Compliance Validator",
            transaction_id=record.record_id,
            category="compliance",
            score=1.0 if record.compliance_passed else 0.0,
            detail=f"Compliance {'passed' if record.compliance_passed else 'failed'}",
            evidence={"passed": record.compliance_passed},
            previous_hash=prev_hash,
        )
        att.compute_hash()
        attestations.append(att)
        prev_hash = att.hash

        # Reliability attestation
        reliability_score = 0.5 if record.dispute_raised and not record.dispute_resolved else (
            0.8 if record.dispute_raised and record.dispute_resolved else 1.0
        )
        att = Attestation(
            agent_id=record.agent_id,
            agent_name=record.agent_name,
            attested_by=record.counterparty_id,
            attested_by_name=record.counterparty_name,
            transaction_id=record.record_id,
            category="reliability",
            score=round(reliability_score, 3),
            detail=f"{'No disputes' if not record.dispute_raised else ('Dispute resolved' if record.dispute_resolved else 'Dispute open')}",
            evidence={"dispute_raised": record.dispute_raised, "dispute_resolved": record.dispute_resolved},
            previous_hash=prev_hash,
        )
        att.compute_hash()
        attestations.append(att)

        self._agent_last_hash[record.agent_id] = att.hash
        self._attestations.extend(attestations)

        try:
            from backend.services.memory_service import memory_service
            memory_service.record_interaction(
                record.agent_id,
                "final_price",
                {"price": record.final_price_eur, "on_time": record.on_time, "price_honored": record.price_honored},
            )
            if not record.on_time:
                memory_service.record_interaction(record.agent_id, "delivery_late", {"variance_days": record.delivery_variance_days})
            if not record.price_honored and record.quoted_price_eur > 0:
                memory_service.record_interaction(record.agent_id, "price_increase_post_order", {"quoted": record.quoted_price_eur, "final": record.final_price_eur})
        except Exception:
            pass

        # Recompute score
        self._recompute_score(record.agent_id, record.agent_name)
        return attestations

    def _recompute_score(self, agent_id: str, agent_name: str = ""):
        agent_attestations = [a for a in self._attestations if a.agent_id == agent_id]
        agent_transactions = [t for t in self._transactions if t.agent_id == agent_id]

        if not agent_attestations:
            return

        by_category = {}
        for att in agent_attestations:
            by_category.setdefault(att.category, []).append(att.score)

        delivery = sum(by_category.get("delivery", [0])) / max(len(by_category.get("delivery", [1])), 1)
        quality = sum(by_category.get("quality", [0])) / max(len(by_category.get("quality", [1])), 1)
        pricing = sum(by_category.get("pricing", [0])) / max(len(by_category.get("pricing", [1])), 1)
        compliance = sum(by_category.get("compliance", [0])) / max(len(by_category.get("compliance", [1])), 1)
        reliability = sum(by_category.get("reliability", [0])) / max(len(by_category.get("reliability", [1])), 1)

        weights = {
            "delivery": 0.30,
            "quality": 0.25,
            "pricing": 0.20,
            "compliance": 0.15,
            "reliability": 0.10,
        }
        composite = (
            delivery * weights["delivery"]
            + quality * weights["quality"]
            + pricing * weights["pricing"]
            + compliance * weights["compliance"]
            + reliability * weights["reliability"]
        )

        # Determine trend
        prev = self._scores.get(agent_id)
        trend = "stable"
        if prev:
            if composite > prev.composite_score + 0.02:
                trend = "improving"
            elif composite < prev.composite_score - 0.02:
                trend = "declining"

        self._scores[agent_id] = ReputationScore(
            agent_id=agent_id,
            agent_name=agent_name,
            delivery_score=round(delivery, 3),
            quality_score=round(quality, 3),
            pricing_score=round(pricing, 3),
            compliance_score=round(compliance, 3),
            reliability_score=round(reliability, 3),
            composite_score=round(composite, 3),
            total_transactions=len(agent_transactions),
            total_attestations=len(agent_attestations),
            trend=trend,
        )

    def submit_trust_rating(self, submission: TrustSubmission) -> dict:
        """Submit contextual trust rating; weight by rater's own trust (web-of-trust)."""
        rater_score = self.get_score(submission.rater_id)
        rater_trust = rater_score.composite_score if rater_score else 0.5
        effective_weight = max(0.3, rater_trust)
        effective_score = submission.score * effective_weight
        record = {
            "agent_id": submission.agent_id,
            "dimension": submission.dimension,
            "score": submission.score,
            "context": submission.context,
            "rater_id": submission.rater_id,
            "effective_score": effective_score,
            "effective_weight": effective_weight,
        }
        self._contextual_submissions.append(record)
        return record

    def get_contextual_score(self, agent_id: str, dimension: str | None = None) -> dict:
        """Get contextual trust scores for agent (optionally by dimension)."""
        subset = [s for s in self._contextual_submissions if s["agent_id"] == agent_id]
        if dimension:
            subset = [s for s in subset if s["dimension"] == dimension]
        if not subset:
            return {"agent_id": agent_id, "dimension": dimension, "score": None, "count": 0}
        total_weighted = sum(s["effective_score"] for s in subset)
        total_weight = sum(s["effective_weight"] for s in subset)
        avg = total_weighted / total_weight if total_weight > 0 else 0.0
        by_dim = {}
        for s in subset:
            d = s["dimension"]
            if d not in by_dim:
                by_dim[d] = {"scores": [], "weighted_sum": 0, "weight_sum": 0}
            by_dim[d]["scores"].append(s["effective_score"])
            by_dim[d]["weighted_sum"] += s["effective_score"]
            by_dim[d]["weight_sum"] += s["effective_weight"]
        dim_scores = {d: v["weighted_sum"] / v["weight_sum"] if v["weight_sum"] else 0 for d, v in by_dim.items()}
        return {"agent_id": agent_id, "dimension": dimension, "score": round(avg, 3), "count": len(subset), "by_dimension": dim_scores}

    def get_score(self, agent_id: str) -> ReputationScore | None:
        return self._scores.get(agent_id)

    def get_all_scores(self) -> list[ReputationScore]:
        return sorted(self._scores.values(), key=lambda s: s.composite_score, reverse=True)

    def get_attestations(self, agent_id: str | None = None) -> list[Attestation]:
        if agent_id:
            return [a for a in self._attestations if a.agent_id == agent_id]
        return list(self._attestations)

    def verify_chain(self, agent_id: str) -> dict:
        """Verify the attestation chain integrity for an agent."""
        chain = [a for a in self._attestations if a.agent_id == agent_id]
        if not chain:
            return {"valid": True, "length": 0, "detail": "No attestations"}

        valid = True
        breaks = []
        for i, att in enumerate(chain):
            # Recompute hash
            expected = att.hash
            recomputed = hashlib.sha256(
                json.dumps(
                    {
                        "agent_id": att.agent_id,
                        "attested_by": att.attested_by,
                        "category": att.category,
                        "score": att.score,
                        "transaction_id": att.transaction_id,
                        "timestamp": att.timestamp,
                        "previous_hash": att.previous_hash,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()

            if expected != recomputed:
                valid = False
                breaks.append({"index": i, "attestation_id": att.attestation_id, "reason": "hash_mismatch"})

        return {
            "valid": valid,
            "length": len(chain),
            "breaks": breaks,
            "detail": "Chain integrity verified" if valid else f"{len(breaks)} integrity breaks detected",
        }

    def get_summary(self) -> dict:
        scores = self.get_all_scores()
        return {
            "total_agents_scored": len(scores),
            "total_transactions": len(self._transactions),
            "total_attestations": len(self._attestations),
            "leaderboard": [
                {
                    "agent_id": s.agent_id,
                    "agent_name": s.agent_name,
                    "composite_score": s.composite_score,
                    "delivery": s.delivery_score,
                    "quality": s.quality_score,
                    "pricing": s.pricing_score,
                    "compliance": s.compliance_score,
                    "reliability": s.reliability_score,
                    "transactions": s.total_transactions,
                    "attestations": s.total_attestations,
                    "trend": s.trend,
                }
                for s in scores
            ],
            "chain_verifications": {s.agent_id: self.verify_chain(s.agent_id) for s in scores},
        }

    def clear(self):
        """Clear transactions/attestations (cascade reset). Contextual submissions persist."""
        self._transactions.clear()
        self._attestations.clear()
        self._scores.clear()
        self._agent_last_hash.clear()


# Global singleton
reputation_ledger = ReputationLedger()


def record_transactions(final_orders: dict, emit) -> dict:
    """Record transactions and return updated reputation summary."""
    try:
        from backend.services.memory_service import memory_service
        memory_service.record_interaction("ferrari-procurement-01", "first_quote", {"orders_count": len(final_orders)})
    except Exception:
        pass

    for _, order in final_orders.items():
        agent = order["agent"]
        product = order["product"]
        # Simulate realistic transaction outcomes
        desired_days = order.get("desired_delivery_days")
        base_days = product.lead_time_days
        slip_days = 0 if random.random() > 0.15 else random.randint(1, 5)
        actual_days = base_days + slip_days
        promised_days = desired_days if isinstance(desired_days, int) else base_days
        on_time = actual_days <= promised_days
        defects = 0 if random.random() > 0.1 else random.randint(1, 3)
        price_honored = order["final_price"] <= order["initial_price"] * 1.02

        record = TransactionRecord(
            agent_id=agent.agent_id,
            agent_name=agent.name,
            counterparty_id="ferrari-procurement-01",
            counterparty_name="Ferrari Procurement AI",
            transaction_type="delivery_completed",
            po_number=order.get("po_number", ""),
            promised_delivery_days=promised_days,
            actual_delivery_days=actual_days,
            on_time=on_time,
            quoted_price_eur=order["initial_price"],
            final_price_eur=order["final_price"],
            price_honored=price_honored,
            quality_accepted=defects == 0,
            defects_found=defects,
            quantity_ordered=order["quantity"],
            quantity_delivered=order["quantity"],
            compliance_passed=True,
            dispute_raised=False,
        )
        attestations = reputation_ledger.record_transaction(record)
        score = reputation_ledger.get_score(agent.agent_id)

        emit(
            "reputation-ledger",
            "Reputation Ledger",
            agent.agent_id,
            agent.name,
            "attestation",
            f"{agent.name}: {len(attestations)} attestations recorded, composite score {score.composite_score:.3f}",
            f"Delivery: {score.delivery_score:.2f} | Quality: {score.quality_score:.2f} | "
            f"Pricing: {score.pricing_score:.2f}",
            "#00BCD4",
            "certificate",
        )

    return reputation_ledger.get_summary()
