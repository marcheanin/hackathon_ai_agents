---
pattern_name: event-driven-architecture
title: Event-Driven Architecture
tags: [async, decoupled, scalable, real-time, reactive, events]
use_cases:
  - real-time data processing
  - systems requiring loose coupling between components
  - audit trails and event sourcing
  - reactive AI pipelines
components:
  - event_broker
  - producers
  - consumers
  - event_store
---

# Event-Driven Architecture

## Description
Event-Driven Architecture (EDA) is a design paradigm where components communicate through the production, detection, and consumption of events. Components are decoupled — producers don't know about consumers.

## Key Components
- **Event Broker**: Central hub for routing events (Kafka, RabbitMQ, NATS)
- **Event Producers**: Components that emit events when state changes
- **Event Consumers**: Components that subscribe to and process events
- **Event Store**: Persistent log of all events (for replay and audit)
- **Dead Letter Queue**: Handles failed event processing

## When to Apply for AI Agents
- AI pipeline where each stage processes events independently
- Agent produces results as events → downstream agents consume them
- Need full audit trail of what each agent did
- Asynchronous long-running agent tasks
- Fan-out patterns: one input triggers multiple parallel agent processes

## Example Component Structure for AI Agent System
```
components:
  - id: event_broker
    type: queue
    technology: Kafka/RabbitMQ
    description: Routes events between agents
  - id: ingestion_agent
    type: llm_agent
    technology: Python + LangChain
    description: Receives user requests, publishes task events
  - id: architecture_agent
    type: llm_agent
    technology: Python + LangGraph
    description: Consumes task events, publishes architecture drafts
  - id: validation_agent
    type: llm_agent
    technology: Python + LangChain
    description: Consumes architecture drafts, publishes validation results
  - id: event_store
    type: database
    technology: PostgreSQL/EventStoreDB
    description: Persists all events for replay
```

## Data Flow
User Request → [Producer] → Event Broker → [Architecture Agent Consumer] → Draft Event → [Validation Consumer] → Result Event

## Trade-offs
- ✅ Loose coupling between agents
- ✅ Natural audit trail
- ✅ Easy to add new consumers without changing producers
- ✅ Handles backpressure well
- ❌ Eventual consistency
- ❌ Harder to debug (distributed traces needed)
- ❌ Message ordering challenges
