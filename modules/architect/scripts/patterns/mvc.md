---
pattern_name: layered-architecture
title: Layered (N-Tier) Architecture
tags: [layered, mvc, monolith, simple, presentation, business-logic, data]
use_cases:
  - simple to medium complexity applications
  - small team projects
  - rapid prototyping
  - hackathon projects
components:
  - presentation_layer
  - business_logic_layer
  - data_access_layer
  - database
---

# Layered (N-Tier) Architecture

## Description
Layered architecture organizes code into horizontal layers, each with a specific responsibility. Each layer only communicates with the layer directly below it. Simple, well-understood, and easy to reason about.

## Layers
- **Presentation Layer**: HTTP handlers, API routes, request/response models
- **Application/Business Logic Layer**: Use cases, domain logic, agent orchestration
- **Infrastructure Layer**: Database access, external API clients, LLM clients
- **Domain Layer** (optional): Core entities and business rules

## When to Apply for AI Agents
- Single-service AI agent with clear separation of concerns
- Small team, fast development needed (hackathon)
- Agent doesn't need complex distribution
- Starting point before evolving to microservices

## Example for AI Agent System
```
components:
  - id: api_layer
    type: api_gateway
    technology: FastAPI
    description: HTTP routes, request validation, response serialization
  - id: agent_service
    type: orchestrator
    technology: LangGraph
    description: Agent orchestration, workflow management
  - id: llm_service
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: LLM interactions, prompt management
  - id: rag_service
    type: tool
    technology: qdrant-client
    description: Vector search, pattern retrieval
  - id: vector_db
    type: database
    technology: Qdrant
    description: Stores architecture pattern embeddings
```

## Trade-offs
- ✅ Simple to understand and develop
- ✅ Fast initial development
- ✅ Easy testing per layer
- ❌ Can become a "big ball of mud" as complexity grows
- ❌ Not ideal for high scalability
- ❌ Tight coupling within layers
