---
pattern_name: cqrs-event-sourcing
title: CQRS + Event Sourcing
tags: [cqrs, event-sourcing, read-model, write-model, audit, history]
use_cases:
  - systems with complex business logic
  - audit requirements (what happened and when)
  - systems where reads and writes have different scaling needs
  - time-travel debugging for AI agent decisions
components:
  - command_handler
  - event_store
  - read_model
  - projections
---

# CQRS + Event Sourcing

## Description
CQRS (Command Query Responsibility Segregation) separates read and write models. Event Sourcing stores all state changes as a sequence of events rather than current state. Combined, they provide full audit history and temporal queries.

## When to Apply for AI Agents
- Need complete audit trail of all agent decisions and iterations
- Different read patterns (get latest architecture vs. get architecture history)
- Replay agent decisions for debugging or retraining
- Multiple consumers need different views of the same data

## Example for AI Agent Builder
```
Write Side (Commands):
  GenerateArchitectureCommand → ArchitectureDraftedEvent
  ValidateArchitectureCommand → ValidationResultEvent
  RetryArchitectureCommand → ArchitectureRetriedEvent

Event Store: all events persisted in order

Read Side (Projections):
  CurrentArchitectureView: latest approved architecture per request
  IterationHistoryView: all drafts and feedback per request
  MetricsView: success rates, average iterations, scores
```

## Trade-offs
- ✅ Complete audit trail
- ✅ Time-travel queries
- ✅ Optimized read/write models
- ❌ Significant complexity
- ❌ Eventual consistency on reads
- ❌ Event schema evolution challenges
