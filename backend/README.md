# Backend Architecture & Execution Flow (Context Reference)

Below is an elaborated, code-grounded report of what happens in `backend/`, with data flows from endpoints → services → adapters/schemas, plus the core logic flow. I’m in Ask mode, so this is informational only.

---

## High-Level Architecture

- **Framework**: FastAPI app that registers routers and serves the frontend.
```python
app = FastAPI(title="Ferrari Supply Chain Agents", version="1.0.0")
...
app.include_router(registry_router)
app.include_router(pubsub_router)
app.include_router(reputation_router)
app.include_router(stream_router)
 ```

**Structure**: Controllers expose HTTP endpoints; services hold domain logic; schemas define data shapes; adapters encapsulate external dependencies (OpenAI).

---

## Entry Points & Endpoint → Service Flows

### 1) Registry / Cascade

Endpoints for agent registration, search, logs, cascade trigger, and disruptions.

```python
@router.post("/registry/register", status_code=201)
async def register_agent(agent: AgentFact):
    return registry.register(agent)

@router.get("/registry/search")
async def search_agents(...):
    results = registry.search(...)
    return results
...
@router.post("/registry/trigger")
async def trigger_cascade(req: TriggerRequest):
    if cascade_state["running"]:
        return JSONResponse(status_code=409, content={"error": "Cascade already running"})
    prepare_new_cascade()
    asyncio.create_task(run_cascade(req.intent, req.budget_eur))
    return {"status": "started", "intent": req.intent}
```

**Flow**:

* `/registry/trigger` → `prepare_new_cascade()` → `run_cascade()` (background task)
* `/registry/register` → `registry.register()`
* `/registry/search` → `registry.search()`
* `/registry/log` → `registry.log_message()` (also feeds SSE stream)

---

### 2) Stream / Live Feed & Report

SSE and cascade state endpoints.

```python
@router.get("/api/stream")
async def stream_messages():
    queue = registry.subscribe()
    ...
    return StreamingResponse(event_generator(), media_type="text/event-stream", ...)

@router.get("/api/report")
async def get_report():
    if cascade_state["report"]:
        return cascade_state["report"]

@router.get("/api/progress")
async def get_progress():
    return {"running": cascade_state["running"], "progress": cascade_state["progress"]}
```

**Flow**:

* `/api/stream` → `registry.subscribe()` → Live messages (`LiveMessage`) pushed via `registry.log_message()`.

---

### 3) Pub/Sub

Event bus introspection endpoints.

```python
@router.get("/api/pubsub/summary")
async def pubsub_summary():
    return event_bus.get_summary()
```

---

### 4) Reputation

Ledger summary and per-agent chain verification.

```python
@router.get("/api/reputation/summary")
async def reputation_summary():
    return reputation_ledger.get_summary()

@router.get("/api/reputation/agent/{agent_id}")
async def reputation_agent(agent_id: str):
    score = reputation_ledger.get_score(agent_id)
    chain = reputation_ledger.verify_chain(agent_id)
    attestations = reputation_ledger.get_attestations(agent_id)
    return {...}
```

---

## Core Services & Data Flow

### Registry (in-memory)

```python
class AgentRegistry:
    def register(self, agent: AgentFact) -> AgentFact: ...
    def search(...): ...
    def log_message(self, msg: LiveMessage): ...
    def subscribe(self) -> asyncio.Queue: ...
```

**Flow**:

* Stores agents in memory.
* Logs messages and pushes them to all SSE subscribers.
* `search()` filters by role, capability, region, certifications, trust.

---

### Agent Service (AI + Seed Agents)

```python
async def ai_reason(...):
    resp = await client.chat.completions.create(...)
    return resp.choices[0].message.content.strip()

async def ai_decompose_bom(intent: str) -> list[dict]:
    resp = await client.chat.completions.create(...)
    return _parse_json_array(...)
...
def create_seed_agents() -> list[AgentFact]:
    return core_agents() + supplier_agents() + logistics_agents() + compliance_agents() + disqualified_agents()
```

**Flow**:

* OpenAI adapter used for reasoning and BOM decomposition.
* Seed agents are assembled from `backend/agents/*`.

---

### Cascade Orchestrator (Main Logic Flow)

```python
async def run_cascade(intent: str, budget_eur: float = BUDGET_CEILING_EUR) -> dict:
    cascade_state["running"] = True
    report = {...}
```

---

## Detailed Logic Flow (Step-by-Step)

### Step 0 — Init & Seed Agents

```python
seed_agents = create_seed_agents()
for agent in seed_agents:
    registry.register(agent)

for agent in seed_agents:
    if agent.status != "active" or (agent.trust and agent.trust.trust_score < TRUST_THRESHOLD):
        continue
    ... event_bus.subscribe(...)
```

---

### Step 1 — Intent → BOM

```python
reasoning = await ai_reason(...)
bom = await ai_decompose_bom(intent)
report["bill_of_materials_summary"] = {...}
```

---

### Step 2 — Discovery & Qualification

```python
candidates = registry.search(role="tier_1_supplier", capability=cat)
if cat in CATEGORY_AGENT_MAP: ... include internal
... filter by trust score
... filter by IATF_16949 certification
... select best by trust
```

---

### Step 3 — Quotes

```python
for cat, agent in qualified_agents.items():
    _emit(... "request_quote" ...)
    reasoning = await ai_reason(...)
    _emit(... "quote_response" ...)
```

---

### Step 4 — Negotiation

```python
... counter offer, supplier counter, final accept ...
report["negotiations"].append(...)
final_orders[cat] = {...}
```

---

### Step 5 — Compliance

```python
... check IATF_16949, sanctions, ESG >= MIN_ESG_SCORE, regulations ...
_emit(... "compliance_result" ...)
report["compliance_summary"] = ...
```

---

### Step 6 — Purchase Orders

```python
... issue PO, confirm, compute ship/delivery dates ...
```

---

### Step 7 — Logistics

```python
logistics_plan, max_lead_days = plan_logistics(final_orders, _emit)
```

and `plan_logistics()` computes routes, costs, and a bottleneck.

```python
def plan_logistics(final_orders: dict, emit, logistics_agent_id: str = "dhl-logistics-01") -> tuple[dict, int]:
    ... emit logistics_request and logistics_proposal ...
```

---

### Step 8 — Disruption Simulation

```python
_emit(... "disruption_alert" ...)
reasoning = await ai_reason(...)
... report["disruptions_handled"].append(...)
```

---

### Step 9 — Reputation / Attestations

```python
report["reputation_summary"] = record_transactions(final_orders, _emit)
```

`record_transactions()` simulates outcomes and writes attestations into the ledger.

```python
def record_transactions(final_orders: dict, emit) -> dict:
    ... reputation_ledger.record_transaction(record) ...
```

---

### Step 10 — Intelligence Feed + Pub/Sub

```python
intel_results = await generate_intelligence_signals(event_bus, count=5)
report["pubsub_summary"] = event_bus.get_summary()
```

`generate_intelligence_signals()` publishes `SupplyChainEvent`s to the event bus and emits intel messages.

```python
async def generate_intelligence_signals(event_bus, count: int = 5) -> list[dict]:
    event = SupplyChainEvent(...)
    recipients = event_bus.publish(event)
    ...
```

---

### Step 11 — Final Report

```python
report["execution_plan"] = {...}
report["graph_nodes"] = nodes
report["graph_edges"] = edges
report["dashboard"] = {...}
report["status"] = "completed"
```

---

## Event Bus / Pub-Sub

```python
class EventBus:
    def subscribe(...): ...
    def publish(self, event: SupplyChainEvent) -> list[str]: ...
    def get_summary(self) -> dict: ...
```

**Flow**:

* Subscriptions are role-based + region/product filters.
* `publish()` routes events to relevant subscribers and tracks deliveries.

---

## Reputation Ledger (Trust Service)

```python
class ReputationLedger:
    def record_transaction(self, record: TransactionRecord) -> list[Attestation]: ...
    def verify_chain(self, agent_id: str) -> dict: ...
    def get_summary(self) -> dict: ...
```

**Flow**:

* Transactions → Attestations (delivery/quality/pricing/compliance/reliability).
* Hash chain verifies integrity.
* Composite scores computed and exposed via API.

---

## Data Models / Schemas

The backbone of request/response and in-memory models:

```python
class AgentFact(BaseModel): ...
class Message(BaseModel): ...
class TriggerRequest(BaseModel): ...
class LiveMessage(BaseModel): ...
class DashboardData(BaseModel): ...
```

---

## External Dependencies / Adapters

OpenAI adapter used by the agent service for reasoning and BOM decomposition.

```python
from openai import AsyncOpenAI
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
def get_async_client() -> AsyncOpenAI:
    return async_client
```

Config for model and thresholds:

```python
OPENAI_MODEL = "gpt-4o-mini"
BUDGET_CEILING_EUR = 500000
TRUST_THRESHOLD = 0.70
MIN_ESG_SCORE = 50
```

---

## Summary of Data Flows

* **HTTP → Controller → Service → Schema/Adapter**

  * `/registry/*` → `registry_controller` → `registry_service` → `AgentFact`, `LiveMessage`
  * `/registry/trigger` → `cascade_service.run_cascade()` → `agent_service`, `registry`, `pubsub`, `trust`, `logistics`, `intelligence`
  * `/api/stream` → `registry.subscribe()` → SSE to clients
  * `/api/reputation/*` → `trust_service.reputation_ledger`

* **Core Logic Flow (cascade)**:

  1. Seed agents → registry
  2. Intent → BOM via OpenAI
  3. Supplier discovery + qualification
  4. Quotes + negotiation
  5. Compliance checks
  6. Purchase orders
  7. Logistics plan
  8. Disruption simulation
  9. Reputation attestations
  10. Intelligence feed + pub/sub summary
  11. Final report / dashboard / graph
---

## Agent Protocol MVP (NANDA-like Simulation)

This repo includes a lightweight agent-to-agent HTTP protocol to simulate a NANDA-like Internet of Agents.

### Discovery

- `GET /api/agents` returns protocol-ready metadata for all registered agents:
  - `agent_id`, `name`, `role`, `status`
  - `endpoint`, `protocol`, `api_version`, `supported_message_types`

### Message Receive Endpoint

- `POST /agent/{agent_id}` accepts an `AgentProtocolMessage` payload and returns an `AgentProtocolReceipt`.
- This is used by the in-repo transport adapter to simulate external delivery.

### Protocol Shapes

`AgentProtocolMessage` (HTTP/JSON):

```json
{
  "protocol_version": "0.1",
  "message_id": "apm-...",
  "conversation_id": "",
  "timestamp": "2026-01-01T00:00:00Z",
  "from_agent": "ferrari-procurement-01",
  "to_agent": "brembo-brake-supplier-01",
  "message_type": "request_quote",
  "payload": { "summary": "...", "detail": "..." },
  "reply_to": "",
  "signature": null
}
```

`AgentProtocolReceipt` (HTTP/JSON):

```json
{
  "protocol_version": "0.1",
  "receipt_id": "apr-...",
  "received_at": "2026-01-01T00:00:00Z",
  "message_id": "apm-...",
  "from_agent": "ferrari-procurement-01",
  "to_agent": "brembo-brake-supplier-01",
  "status": "accepted",
  "detail": "Message received"
}
```

### Transport Toggle + Signing

- `ENABLE_EXTERNAL_AGENT_TRANSPORT=true` enables HTTP delivery alongside SSE logging.
- `AGENT_PROTOCOL_SECRET=...` enables HMAC signature on outbound messages and verification on receive.

### Example (curl)

```bash
curl -X POST http://localhost:8000/agent/brembo-brake-supplier-01 \
  -H "Content-Type: application/json" \
  -d '{"protocol_version":"0.1","message_id":"apm-123","from_agent":"ferrari-procurement-01","to_agent":"brembo-brake-supplier-01","message_type":"request_quote","payload":{"summary":"Quote request"},"reply_to":""}'
```
