"""Swappable negotiation strategies — speed-first, cost-first, trust-first."""

from __future__ import annotations

import random
from typing import Protocol


class NegotiationParams:
    """Output of a strategy for one negotiation round."""

    def __init__(
        self,
        discount_ask_min: float,
        discount_ask_max: float,
        max_rounds: int,
        accept_sooner: bool,
        aggressive_counter: bool,
    ):
        self.discount_ask_min = discount_ask_min
        self.discount_ask_max = discount_ask_max
        self.max_rounds = max_rounds
        self.accept_sooner = accept_sooner
        self.aggressive_counter = aggressive_counter


class NegotiationStrategy(Protocol):
    """Protocol for negotiation strategies."""

    def get_params(self, agent_trust_score: float | None) -> NegotiationParams:
        """Return negotiation parameters for this strategy."""
        ...


class SpeedFirstStrategy:
    """Fewer rounds, accept sooner, higher final price."""

    def get_params(self, agent_trust_score: float | None) -> NegotiationParams:
        return NegotiationParams(
            discount_ask_min=1.0,
            discount_ask_max=3.0,
            max_rounds=1,
            accept_sooner=True,
            aggressive_counter=False,
        )


class CostFirstStrategy:
    """Current behavior: 3 rounds, split difference."""

    def get_params(self, agent_trust_score: float | None) -> NegotiationParams:
        return NegotiationParams(
            discount_ask_min=3.0,
            discount_ask_max=7.0,
            max_rounds=3,
            accept_sooner=False,
            aggressive_counter=True,
        )


class TrustFirstStrategy:
    """Prefer high-trust suppliers; fewer counter-offers to trusted agents."""

    def get_params(self, agent_trust_score: float | None) -> NegotiationParams:
        trust = agent_trust_score or 0.0
        if trust >= 0.9:
            return NegotiationParams(
                discount_ask_min=0.0,
                discount_ask_max=2.0,
                max_rounds=1,
                accept_sooner=True,
                aggressive_counter=False,
            )
        if trust >= 0.75:
            return NegotiationParams(
                discount_ask_min=1.0,
                discount_ask_max=4.0,
                max_rounds=2,
                accept_sooner=True,
                aggressive_counter=False,
            )
        return NegotiationParams(
            discount_ask_min=2.0,
            discount_ask_max=6.0,
            max_rounds=3,
            accept_sooner=False,
            aggressive_counter=True,
        )


STRATEGIES: dict[str, type[NegotiationStrategy]] = {
    "speed-first": SpeedFirstStrategy,
    "cost-first": CostFirstStrategy,
    "trust-first": TrustFirstStrategy,
}


def get_strategy(name: str) -> NegotiationStrategy:
    """Get strategy by name."""
    cls = STRATEGIES.get(name, CostFirstStrategy)
    return cls()


def apply_strategy(
    strategy: NegotiationStrategy,
    initial_price: float,
    agent_trust_score: float | None,
) -> tuple[float, float, float, int]:
    """Apply strategy to produce offer_price, counter_price, final_price, rounds."""
    params = strategy.get_params(agent_trust_score)
    discount_ask = random.uniform(params.discount_ask_min, params.discount_ask_max)
    offer_price = round(initial_price * (1 - discount_ask / 100), 2)

    if params.max_rounds <= 1:
        if params.accept_sooner:
            # Accept at ~95% of initial
            final_price = round(initial_price * 0.95, 2)
            return offer_price, final_price, final_price, 1
        final_price = round((offer_price + initial_price) / 2, 2)
        return offer_price, final_price, final_price, 1

    supplier_discount = discount_ask * (0.4 if params.aggressive_counter else 0.6)
    counter_price = round(initial_price * (1 - supplier_discount / 100), 2)
    final_price = round((offer_price + counter_price) / 2, 2)
    return offer_price, counter_price, final_price, min(params.max_rounds, 3)
