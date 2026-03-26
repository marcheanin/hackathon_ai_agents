"""
Node 2: Pattern Selector
Выполняется ОДИН РАЗ после RAG retrieval.
LLM выбирает 2-3 наиболее релевантных паттерна из RAG-результатов.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.llm.client import get_llm_json
from app.llm.json_utils import parse_llm_json


class PatternSelection(BaseModel):
    selected_patterns: list[str] = Field(
        ..., description="Названия (pattern_name) 2-3 выбранных паттернов"
    )
    primary_pattern: str = Field(
        ..., description="Главный паттерн — наиболее подходящий"
    )
    reasoning: str = Field(
        ..., description="Краткое обоснование выбора паттернов (1-3 предложения)"
    )


SYSTEM_PROMPT = """You are a software architect. Select the 2-3 most relevant architectural patterns for the given user request from the provided list.

You MUST respond with ONLY a valid JSON object, no other text:
{
  "selected_patterns": ["pattern_name_1", "pattern_name_2"],
  "primary_pattern": "pattern_name_1",
  "reasoning": "Brief explanation of why these patterns fit the request"
}

Use only pattern_name values from the provided list. Do not output anything except the JSON object."""


async def select_patterns_node(state: AgentState) -> dict:
    llm = get_llm_json()

    patterns_summary = "\n".join(
        f"- {p['pattern_name']}: {p['title']} (score: {p['score']:.2f}, tags: {', '.join(p['tags'][:4])})"
        for p in state["retrieved_patterns"]
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"User request: {state['user_request']}\n\nAvailable patterns:\n{patterns_summary}"
        ),
    ]

    response = await llm.ainvoke(messages)
    result = PatternSelection(**parse_llm_json(response))

    return {
        "selected_patterns": result.selected_patterns,
        "primary_pattern": result.primary_pattern,
        "pattern_reasoning": result.reasoning,
    }
