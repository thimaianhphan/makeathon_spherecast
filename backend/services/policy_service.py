"""Policy-as-Code for agents — evaluate plans against policy spec."""

from __future__ import annotations

from backend.schemas import PolicySpec, PolicyEvaluation


DEFAULT_POLICY = PolicySpec(
    jurisdiction="EU",
    max_risk_score=0.7,
    min_trust_score=0.70,
    min_esg_score=50,
    forbid_single_supplier=False,
)


class PolicyService:
    """Evaluate execution plans against policy."""

    def __init__(self, policy: PolicySpec | None = None):
        self._policy = policy or DEFAULT_POLICY

    def get_policy(self) -> PolicySpec:
        return self._policy

    def set_policy(self, policy: PolicySpec):
        self._policy = policy

    def evaluate_policy(self, plan: dict) -> PolicyEvaluation:
        """Evaluate plan against policy; return compliant, violations, explanations."""
        violations = []
        explanations = []

        # Check min_trust for suppliers (qualified_agents can be {category: agent} or {agent_id: agent})
        qualified = plan.get("qualified_agents")
        if isinstance(qualified, dict):
            for key, agent in qualified.items():
                agent_id = getattr(agent, "agent_id", key)
                trust = agent.trust.trust_score if hasattr(agent, "trust") and agent.trust else 0
                if trust < self._policy.min_trust_score:
                    violations.append({"rule": "min_trust_score", "agent_id": agent_id, "value": trust})
                    explanations.append(f"Agent {agent_id} trust {trust} below minimum {self._policy.min_trust_score}")

        # Check risk_assessment
        risk_assessment = plan.get("execution_plan", {}).get("risk_assessment", {})
        overall_risk = risk_assessment.get("overall_risk", "low")
        risk_map = {"low": 0.2, "medium": 0.5, "high": 0.8}
        risk_val = risk_map.get(overall_risk, 0.5)
        if risk_val > self._policy.max_risk_score:
            violations.append({"rule": "max_risk_score", "value": risk_val})
            explanations.append(f"Risk {overall_risk} ({risk_val}) exceeds max {self._policy.max_risk_score}")

        # Check forbid_single_supplier: if only 1 supplier for a category, flag
        if self._policy.forbid_single_supplier:
            discovery = plan.get("discovery_results", {})
            paths = discovery.get("discovery_paths", [])
            for p in paths:
                if p.get("results_count", 0) == 1:
                    violations.append({"rule": "forbid_single_supplier", "need": p.get("need")})
                    explanations.append(f"Single supplier for {p.get('need')} — policy forbids single-source")

        compliant = len(violations) == 0
        return PolicyEvaluation(compliant=compliant, violations=violations, explanations=explanations)


policy_service = PolicyService()
