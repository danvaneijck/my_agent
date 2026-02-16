# Architecture Documentation

System-wide architecture, design decisions, and infrastructure documentation.

## Purpose

This directory contains high-level architectural documentation explaining how the agent system is designed, how components interact, and the rationale behind key design decisions.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Overview](overview.md) | Complete system architecture and design | Understanding overall system design |
| [Data Flow](data-flow.md) | Request/response lifecycles with diagrams | Debugging message flows |
| [Database Schema](database-schema.md) | Complete schema with relationships | Working with database |
| [Module System](module-system.md) | Module architecture and discovery | Understanding module system |
| [Deployment](deployment.md) | Docker infrastructure and networking | Configuring infrastructure |

## Key Concepts

- **Microservice Architecture**: Each module is an independent FastAPI service
- **Agent Loop**: The core reasoning cycle that powers the agent
- **Tool Discovery**: Dynamic module discovery via HTTP manifests
- **Message Flow**: Platform bot → Core → Modules → Core → Platform bot
- **Data Persistence**: PostgreSQL + Redis + MinIO storage

## Related Documentation

- [Core Services](../core/) — Internal implementation details
- [Modules](../modules/) — Individual module documentation
- [Deployment](../deployment/) — Production deployment guides

---

[Back to Documentation Index](../INDEX.md)
