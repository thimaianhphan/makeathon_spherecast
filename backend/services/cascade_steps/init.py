"""Cascade step: initialize registry and pubsub subscriptions."""

from __future__ import annotations

import asyncio

from backend.services.agent_service import create_seed_agents
from backend.services.registry_service import registry
from backend.services.pubsub_service import event_bus
from backend.config import TRUST_THRESHOLD


async def run_init(emit):
    emit(
        "system",
        "System",
        "registry",
        "Agent Registry",
        "system",
        summary=None,
        payload={"summary": "Initializing agent network...", "detail": "Registering all supply chain agents"},
    )

    event_bus.clear()

    seed_agents = create_seed_agents()
    for agent in seed_agents:
        registry.register(agent)

    for agent in seed_agents:
        if agent.status != "active" or (agent.trust and agent.trust.trust_score < TRUST_THRESHOLD):
            continue
        regions = []
        product_cats = []
        if agent.location and agent.location.headquarters:
            regions.append(agent.location.headquarters.country)
        if agent.location and agent.location.shipping_regions:
            regions.extend(agent.location.shipping_regions)
        for p in agent.capabilities.products:
            product_cats.append(p.category)
        event_bus.subscribe(
            agent.agent_id,
            agent.name,
            agent.role,
            regions=list(set(regions)),
            product_categories=list(set(product_cats)),
        )

    emit(
        "system",
        "System",
        "registry",
        "Agent Registry",
        "pubsub_init",
        summary=None,
        payload={"summary": f"Event bus initialized: {len(event_bus.list_subscriptions())} agents subscribed"},
    )

    await asyncio.sleep(0.3)
    return seed_agents
