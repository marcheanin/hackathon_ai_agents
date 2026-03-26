---
pattern_name: hexagonal-architecture
title: Hexagonal Architecture (Ports & Adapters)
tags: [hexagonal, ports-adapters, clean-architecture, testable, domain-driven]
use_cases:
  - systems requiring high testability
  - applications with multiple integration points
  - domain logic that must be isolated from infrastructure
  - systems that swap databases or LLM providers
components:
  - domain_core
  - ports
  - adapters
  - application_services
---

# Hexagonal Architecture (Ports & Adapters)

## Description
Hexagonal Architecture isolates the core domain logic from external systems. The domain communicates with the outside world through Ports (interfaces) and Adapters (implementations). This makes it easy to swap external dependencies (LLM providers, databases) without changing core logic.

## Key Components
- **Domain Core**: Business logic, completely independent of external systems
- **Ports (Interfaces)**: Define how the domain communicates with the outside
  - Primary/Driving Ports: How external actors invoke the domain (API, CLI)
  - Secondary/Driven Ports: How domain invokes external systems (DB, LLM)
- **Adapters**: Concrete implementations of ports
  - Primary Adapters: REST API, gRPC, CLI
  - Secondary Adapters: Qdrant adapter, Ollama adapter, PostgreSQL adapter

## When to Apply for AI Agents
- Agent logic must be testable without real LLM/DB
- Need to swap Ollama for OpenAI without changing agent logic
- Multiple interfaces to the agent (REST API + CLI + message queue)
- Domain logic is complex and needs isolation

## Example Component Structure for AI Agent System
```
components:
  - id: agent_domain
    type: orchestrator
    description: Core agent logic (pattern selection, generation, validation)
  - id: llm_port
    type: tool
    description: Interface - generate_text(prompt) -> str
  - id: retriever_port
    type: tool
    description: Interface - retrieve_patterns(query) -> list[Pattern]
  - id: ollama_adapter
    type: external
    technology: Ollama + langchain-openai
    description: Implements LLM port for local Ollama
  - id: openai_adapter
    type: external
    technology: OpenAI API
    description: Alternative LLM port implementation
  - id: qdrant_adapter
    type: database
    technology: Qdrant
    description: Implements retriever port
  - id: rest_adapter
    type: api_gateway
    technology: FastAPI
    description: Primary adapter - exposes agent via HTTP
```

## Trade-offs
- ✅ Excellent testability (mock ports in tests)
- ✅ Easy to swap implementations (Ollama ↔ OpenAI)
- ✅ Domain logic is clean and focused
- ❌ More abstraction layers
- ❌ Overkill for simple agents
