# Architecture Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) — rendered natively in GitHub, GitLab, and most Markdown previewers.

| File | What it shows |
|------|--------------|
| [01-system-overview.md](01-system-overview.md) | Top-level: frontend · backend · DB · external services |
| [02-backend-api.md](02-backend-api.md) | All 11 routers and their endpoints |
| [03-sourcing-pipeline.md](03-sourcing-pipeline.md) | 4-stage LLM pipeline + greedy batch endpoint |
| [04-database-schema.md](04-database-schema.md) | SQLite ER diagram + file-based caches |
| [05-frontend-architecture.md](05-frontend-architecture.md) | Pages · components · state management |
| [06-cascade-orchestration.md](06-cascade-orchestration.md) | 12-step multi-agent cascade + agent registry |
| [07-data-flow.md](07-data-flow.md) | Sequence diagrams for the two main user flows |
| [08-deployment.md](08-deployment.md) | Docker build · dev setup · service dependencies |
