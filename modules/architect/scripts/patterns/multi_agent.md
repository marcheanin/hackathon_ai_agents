---
pattern_name: multi-agent-orchestration
title: Multi-Agent Orchestration Pattern
tags: [multi-agent, orchestration, langgraph, pipeline, specialization, ai-agent]
use_cases:
  - complex tasks requiring specialized expertise
  - parallel processing of subtasks
  - systems with validation and retry loops
  - ai agent builders
components:
  - orchestrator
  - specialized_agents
  - shared_state
  - communication_channel
---

# Multi-Agent Orchestration Pattern

## Description
Multiple specialized AI agents work together under the coordination of an orchestrator. Each agent handles a specific subtask, and the orchestrator manages the workflow, state, and routing between agents.

## Key Components
- **Orchestrator**: Controls the flow, decides which agent to invoke next (LangGraph StateGraph)
- **Specialized Agents**: Each focuses on one task (RAG retrieval, generation, validation)
- **Shared State**: Common data structure all agents read/write (TypedDict in LangGraph)
- **Retry Coordinator**: Handles failure cases and re-invokes agents with feedback

## Orchestration Patterns
1. **Sequential Pipeline**: Agent A → Agent B → Agent C
2. **Parallel Fan-out**: Orchestrator → [Agent A, Agent B] → merge results
3. **Conditional Routing**: Based on output, route to different agents
4. **Retry Loop**: Agent → Validator → (if fail) → Agent (with feedback)

## LangGraph Implementation for AI Architect System
```
State: AgentState (TypedDict)
  - user_request, retrieved_patterns
  - selected_patterns, components, data_flows
  - mermaid_diagram, validation_result
  - feedback_history, iteration_count

Graph Nodes:
  1. retrieve_patterns    → RAG search (no LLM)
  2. select_patterns      → LLM chooses best patterns
  3. design_components    → LLM designs component list (RETRYABLE)
  4. design_integrations  → LLM designs data flows (RETRYABLE)
  5. synthesize_diagram   → Python generates Mermaid (no LLM)
  6. validate_architecture → LLM validates (triggers retry or END)

Conditional Edges:
  validate → approved → END
  validate → rejected + iter < MAX → design_components (with feedback)
  validate → rejected + iter >= MAX → END (max_retries)
```

## Example Component Structure
```
components:
  - id: graph_orchestrator
    type: orchestrator
    technology: LangGraph StateGraph
    description: Manages agent pipeline and retry loop
  - id: rag_retriever
    type: tool
    technology: Qdrant + embedding model
    description: Retrieves relevant architecture patterns
  - id: pattern_selector
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: Selects most relevant patterns (runs once)
  - id: component_architect
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: Designs component list (retryable)
  - id: integration_designer
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: Designs data flows (retryable)
  - id: diagram_synthesizer
    type: tool
    technology: Python (deterministic)
    description: Generates Mermaid diagram without LLM
  - id: arch_validator
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: Validates architecture draft, provides feedback
```

## Trade-offs
- ✅ Each agent is focused and reliable
- ✅ Retry at task level, not full restart
- ✅ Interpretable intermediate results
- ✅ Easy to add new specialized agents
- ❌ More complex than single-agent
- ❌ State management overhead
- ❌ Multiple LLM calls (higher latency)
