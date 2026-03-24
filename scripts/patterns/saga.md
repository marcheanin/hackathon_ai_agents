---
pattern_name: saga-pattern
title: Saga Pattern (Distributed Transactions)
tags: [saga, distributed, compensation, long-running, orchestration, choreography]
use_cases:
  - multi-step workflows spanning multiple services
  - long-running processes requiring compensation on failure
  - distributed transactions without two-phase commit
  - AI agent workflows with rollback requirements
components:
  - saga_orchestrator
  - saga_steps
  - compensation_handlers
  - saga_log
---

# Saga Pattern

## Description
The Saga pattern manages distributed transactions as a sequence of local transactions. If a step fails, compensating transactions are executed to undo previous steps. Two variants: Choreography (event-driven) and Orchestration (central coordinator).

## When to Apply for AI Agents
- Multi-step agent workflow that must be rolled back on failure
- Agent pipeline that calls external services (code repos, cloud APIs)
- Need to track partial completions and resume from failure point
- Long-running architecture generation with intermediate saves

## Example for AI Agent Builder (Orchestration Saga)
```
Saga: GenerateAgentArchitecture

Step 1: RetrievePatterns
  - Action: Query Qdrant
  - Compensation: (no rollback needed)

Step 2: GenerateArchitecture
  - Action: LLM generates draft
  - Compensation: Delete draft from store

Step 3: ValidateArchitecture
  - Action: LLM validates
  - Compensation: Mark as invalidated

Step 4: StoreResult
  - Action: Save to results DB
  - Compensation: Delete from results DB

On failure at Step N: execute compensations N-1 → 1
```

## Trade-offs
- ✅ Handles partial failures in distributed workflows
- ✅ No distributed locking needed
- ✅ Works with eventual consistency
- ❌ Complex compensation logic
- ❌ Difficult to implement correctly
- ❌ Saga log adds overhead
