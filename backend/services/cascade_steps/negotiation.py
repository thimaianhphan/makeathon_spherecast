"""Cascade step: negotiation."""

from __future__ import annotations

from backend.services.agent_service import ai_reason
from backend.services.negotiation_strategies import get_strategy, apply_strategy
from backend.services.memory_service import memory_service


async def run_negotiation(quotes: dict, report: dict, emit, ts, strategy: str) -> dict:
    neg_strategy = get_strategy(strategy)
    final_orders = {}
    for cat, quote in quotes.items():
        agent = quote["agent"]
        product = quote["product"]
        initial_price = quote["initial_price"]

        if agent.trust and agent.trust.ferrari_tier_status == "internal":
            final_orders[cat] = {**quote, "final_price": initial_price, "discount_pct": 0}
            continue

        agent_trust = agent.trust.trust_score if agent.trust else None
        offer_price, counter_price, final_price, rounds = apply_strategy(
            neg_strategy, initial_price, agent_trust
        )
        final_discount = round((1 - final_price / initial_price) * 100, 2)
        discount_ask = round((1 - offer_price / initial_price) * 100, 2)
        supplier_discount = round((1 - counter_price / initial_price) * 100, 2)

        behavioral = memory_service.get_behavioral_signal(agent.agent_id)
        memory_context = f" Past signal: {behavioral}. " if behavioral else " "

        reasoning = await ai_reason(
            "Ferrari Procurement AI",
            "procurement_agent",
            f"{agent.name} quoted EUR {initial_price} for {product.name}.{memory_context}Strategy: {strategy}. Counter offer EUR {offer_price} ({discount_ask:.1f}% discount).",
        )
        report["reasoning_log"].append({"agent": "Ferrari Procurement", "timestamp": ts(), "thought": reasoning})

        emit(
            "ferrari-procurement-01",
            "Ferrari Procurement",
            agent.agent_id,
            agent.name,
            "negotiate",
            summary=None,
            payload={
                "offer_price_eur": offer_price,
                "discount_pct": discount_ask,
                "reason": f"Strategy: {strategy}",
                "ai_reasoning": reasoning,
            },
        )

        if rounds >= 2:
            reasoning = await ai_reason(
                agent.name,
                agent.role,
                f"Ferrari counter-offered EUR {offer_price}. Your floor allows ~{supplier_discount:.1f}% discount. Counter at EUR {counter_price}.",
            )
            report["reasoning_log"].append({"agent": agent.name, "timestamp": ts(), "thought": reasoning})
            emit(
                agent.agent_id,
                agent.name,
                "ferrari-procurement-01",
                "Ferrari Procurement",
                "negotiate_response",
                summary=None,
                payload={
                    "counter_price_eur": counter_price,
                    "discount_pct": supplier_discount,
                    "reason": "Material costs limit flexibility",
                    "ai_reasoning": reasoning,
                },
            )

        reasoning = await ai_reason(
            "Ferrari Procurement AI",
            "procurement_agent",
            f"Agreed at EUR {final_price}. Within budget. Accept.",
        )
        report["reasoning_log"].append({"agent": "Ferrari Procurement", "timestamp": ts(), "thought": reasoning})
        emit(
            "ferrari-procurement-01",
            "Ferrari Procurement",
            agent.agent_id,
            agent.name,
            "negotiate",
            summary=None,
            payload={
                "offer_price_eur": final_price,
                "discount_pct": final_discount,
                "reason": "Deal within budget ceiling",
                "ai_reasoning": reasoning,
            },
        )

        negotiation_log = [
            {"round": 1, "from": "ferrari-procurement-01", "action": "counter_offer", "value_eur": offer_price, "reasoning": f"Strategy {strategy}"},
        ]
        if rounds >= 2:
            negotiation_log.append({"round": 2, "from": agent.agent_id, "action": "counter_offer", "value_eur": counter_price, "reasoning": "Supplier counter"})
        negotiation_log.append({"round": len(negotiation_log) + 1, "from": "ferrari-procurement-01", "action": "accept", "value_eur": final_price, "reasoning": "Accepted"})

        report["negotiations"].append(
            {
                "with_agent": agent.agent_id,
                "with_name": agent.name,
                "product": product.name,
                "rounds": rounds,
                "initial_ask_eur": initial_price,
                "initial_offer_eur": offer_price,
                "final_agreed_eur": final_price,
                "discount_pct": final_discount,
                "negotiation_log": negotiation_log,
            }
        )

        final_orders[cat] = {**quote, "final_price": final_price, "discount_pct": final_discount}

    return final_orders
