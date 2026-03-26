from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

try:
    from langgraph.graph import END, StateGraph
    _HAS_LANGGRAPH = True
except ModuleNotFoundError:  # pragma: no cover
    END = None  # type: ignore
    StateGraph = None  # type: ignore
    _HAS_LANGGRAPH = False

from analyst.config import (
    MAX_ITERATIONS,
    SUFFICIENCY_THRESHOLD,
)
from analyst.chains.architecture_proposal import propose_architecture
from analyst.chains.agent_match import evaluate_agent_match
from analyst.chains.clarification import generate_clarification
from analyst.chains.domain_routing import route_domain
from analyst.chains.entities import extract_entities
from analyst.chains.intent import classify_intent
from analyst.chains.requirements import build_dynamic_requirements
from analyst.chains.sufficiency import evaluate_sufficiency
from analyst.enrichment.enricher import ContextEnricher
from analyst.models.agents import AgentMatch
from analyst.models.context import DomainCandidate, DomainLink, EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.models.enums import ConcretizedDecision, IntentType
from analyst.models.snippets import SnippetSummary
from analyst.observability import pipeline_log
from analyst.synthesis.redirect import build_redirect_response
from analyst.synthesis.synthesizer import synthesize_request


class AnalystState(TypedDict):
    session_id: str
    latest_user_message: str

    # Conversation & pipeline state
    messages: list[dict[str, Any]]
    iteration: int

    extracted_entities: ExtractedEntities
    domain: DomainInfo | None
    enriched_context: EnrichedContext
    domain_candidates: list[dict[str, Any]]
    cross_domain_links: list[dict[str, Any]]
    dynamic_requirements: list[dict[str, Any]]

    agent_matches: list[AgentMatch]
    snippet_matches: list[SnippetSummary]

    sufficiency_score: int | None
    gaps: list[str]
    already_asked: list[str]

    # Routing helpers
    agent_match_decision: NotRequired[Literal["exact", "partial", "none"]]
    pending_redirect_agent_match: NotRequired[AgentMatch | None]
    pending_redirect: NotRequired[bool]
    force_finalize: NotRequired[bool]

    # Output
    output: NotRequired[dict[str, Any]]


def _merge_entities(existing: ExtractedEntities, incoming: ExtractedEntities, merge_strategy: str) -> ExtractedEntities:
    if merge_strategy == "overwrite":
        # В mock-режиме entity_extractor часто не заполняет `intent`, но остальные поля (capabilities/nfr/...) должны быть взяты из `incoming`.
        if incoming.intent is None:
            return incoming.model_copy(update={"intent": existing.intent})
        return incoming

    # append merge
    merged_capabilities = sorted(set((existing.capabilities or []) + (incoming.capabilities or [])))
    merged_business = list(existing.business_requirements or []) + list(incoming.business_requirements or [])

    # NFR обновляем, если есть хотя бы одно заполненное поле
    merged_nfr = incoming.nfr if incoming.nfr is not None else existing.nfr

    return existing.model_copy(
        update={
            "capabilities": merged_capabilities,
            "business_requirements": merged_business,
            "system_name": incoming.system_name or existing.system_name,
            "nfr": merged_nfr,
            "integrations": list(existing.integrations or []) + list(incoming.integrations or []),
            "constraints": incoming.constraints or existing.constraints,
            "technologies": list(existing.technologies or []) + list(incoming.technologies or []),
            "features": list(existing.features or []) + list(incoming.features or []),
            "limit": incoming.limit or existing.limit,
            # Поля из checklist_templates.json (должны поддерживать append)
            "transfer_mode": incoming.transfer_mode or existing.transfer_mode,
            "limit_or_amount_rules": incoming.limit_or_amount_rules or existing.limit_or_amount_rules,
            "sms_confirm": incoming.sms_confirm if incoming.sms_confirm is not None else existing.sms_confirm,
            "aml_check_threshold": incoming.aml_check_threshold or existing.aml_check_threshold,
            "auto_cancel_after_minutes": (
                incoming.auto_cancel_after_minutes
                if incoming.auto_cancel_after_minutes is not None
                else existing.auto_cancel_after_minutes
            ),
            "pending_policy": incoming.pending_policy or existing.pending_policy,
            "rollback_strategy": incoming.rollback_strategy or existing.rollback_strategy,
            "intent": existing.intent or incoming.intent,
        }
    )


class AnalystOrchestrator:
    """LangGraph orchestrator для модуля «ИИ Аналитик»."""

    def __init__(self) -> None:
        self._enricher = ContextEnricher()
        self._graph = self._build_graph() if _HAS_LANGGRAPH else None

    def _build_graph(self):
        g: StateGraph[AnalystState] = StateGraph(AnalystState)

        async def receive_message(state: AnalystState) -> dict[str, Any]:
            pipeline_log(
                state["session_id"],
                "orchestrator.node",
                "receive_message",
                history_len=len(state.get("messages") or []),
                message_preview=(state["latest_user_message"] or "")[:160],
            )
            messages = list(state["messages"])
            messages.append({"role": "user", "text": state["latest_user_message"]})
            return {"messages": messages}

        async def handle_pending_redirect(state: AnalystState) -> dict[str, Any]:
            agent_match = state.get("pending_redirect_agent_match")
            latest = (state["latest_user_message"] or "").lower()

            pipeline_log(
                state["session_id"],
                "orchestrator.node",
                "handle_pending_redirect_enter",
                has_agent_match=agent_match is not None,
                agent_id=getattr(agent_match, "agent_id", None),
            )

            # Heuristics: клиент выбирает "redirect", если упоминает редирект/доступ/перенаправить
            wants_redirect = any(
                k in latest
                for k in [
                    "redirect",
                    "перенаправ",
                    "дать доступ",
                    "получить доступ",
                    "да,",
                    "да",
                    "использовать существующий",
                ]
            )

            if not agent_match:
                # Страховка: если state поврежден, продолжаем обычный пайплайн
                pipeline_log(state["session_id"], "orchestrator.node", "handle_pending_redirect", outcome="clear_flags_no_match")
                return {"pending_redirect": False, "pending_redirect_agent_match": None}

            if wants_redirect:
                redirect_response = build_redirect_response(state["enriched_context"], agent_match)
                pipeline_log(
                    state["session_id"],
                    "orchestrator.node",
                    "handle_pending_redirect",
                    outcome="user_chose_redirect",
                    agent_id=agent_match.agent_id,
                    wants_redirect=True,
                )
                return {
                    "pending_redirect": False,
                    "pending_redirect_agent_match": None,
                    "output": {"kind": "redirect", "redirect_response": redirect_response.model_dump()},
                }

            # build path (downgrade) -> чистим флаги и идем в sufficiency
            pipeline_log(
                state["session_id"],
                "orchestrator.node",
                "handle_pending_redirect",
                outcome="user_chose_build_downgrade_to_partial",
                wants_redirect=False,
            )
            return {
                "pending_redirect": False,
                "pending_redirect_agent_match": None,
                "agent_match_decision": "partial",
            }

        async def classify_intent_node(state: AnalystState) -> dict[str, Any]:
            res = await classify_intent(user_message=state["latest_user_message"], conversation_history=state["messages"])
            pipeline_log(
                state["session_id"],
                "chain.intent",
                "classify_intent",
                intent=str(res.intent),
                confidence=round(res.confidence, 4),
                reasoning_preview=(res.reasoning or "")[:120],
            )
            entities = state["extracted_entities"].model_copy(update={"intent": res.intent})
            return {"extracted_entities": entities}

        async def extract_entities_node(state: AnalystState) -> dict[str, Any]:
            res = await extract_entities(
                user_message=state["latest_user_message"],
                conversation_history=state["messages"],
                existing_entities=state["extracted_entities"],
                domain_hint=None,
            )
            pipeline_log(
                state["session_id"],
                "chain.entities",
                "extract_entities",
                merge_strategy=res.merge_strategy,
                incoming_caps=len(res.entities.capabilities or []),
            )
            merge_strategy = res.merge_strategy
            # Если клиент отвечает про NFR/политику и в сообщении нет capabilities,
            # не считаем это сменой темы: preserve уже извлеченные capabilities.
            if merge_strategy == "overwrite" and not (res.entities.capabilities or []):
                merge_strategy = "append"
            merged = _merge_entities(state["extracted_entities"], res.entities, merge_strategy)
            pipeline_log(
                state["session_id"],
                "chain.entities",
                "extract_entities_merged",
                capabilities=list(merged.capabilities or [])[:20],
                capabilities_total=len(merged.capabilities or []),
            )
            return {"extracted_entities": merged}

        async def detect_domain_node(state: AnalystState) -> dict[str, Any]:
            routed = await route_domain(
                user_message=state["latest_user_message"],
                extracted_entities=state["extracted_entities"],
                conversation_history=state["messages"],
            )
            domain = routed.primary
            pipeline_log(
                state["session_id"],
                "chain.domain",
                "detect_domain",
                domain=domain.domain,
                sub_domain=domain.sub_domain,
                confidence=round(domain.confidence, 4) if domain.confidence is not None else None,
                alternatives=[a.model_dump() for a in routed.alternatives],
            )
            return {
                "domain": domain,
                "domain_candidates": [a.model_dump() for a in routed.alternatives],
                "cross_domain_links": [l.model_dump() for l in routed.cross_domain_links],
            }

        async def enrich_context_node(state: AnalystState) -> dict[str, Any]:
            if state["domain"] is None:
                # Плохое состояние; fallback
                pipeline_log(state["session_id"], "enrichment", "enrich_context_skipped", reason="domain_is_none")
                return {}
            enriched = await self._enricher.enrich_context(
                state["domain"],
                state["extracted_entities"],
                session_id=state["session_id"],
            )
            enriched.domain_candidates = [DomainCandidate.model_validate(c) for c in state.get("domain_candidates", [])]
            enriched.cross_domain_links = [DomainLink.model_validate(c) for c in state.get("cross_domain_links", [])]
            enriched.dynamic_requirements = []
            return {
                "enriched_context": enriched,
                "agent_matches": enriched.agent_matches or [],
                "snippet_matches": enriched.snippet_matches or [],
            }

        async def evaluate_agent_match_node(state: AnalystState) -> dict[str, Any]:
            enriched = state["enriched_context"]
            if state["domain"] is None:
                pipeline_log(state["session_id"], "chain.agent_match", "evaluate_agent_match", decision="none", reason="no_domain")
                return {"agent_match_decision": "none", "agent_matches": []}

            res = await evaluate_agent_match(extracted_entities=state["extracted_entities"], candidate_agents=enriched.agent_candidates)

            enriched2 = enriched.model_copy(deep=True)
            enriched2.agent_matches = res.matches

            # Offer redirect_choice only when a single best agent fully covers requirements.
            # If there are uncovered capabilities, we want sufficiency+synthesis to reuse multiple existing agents.
            if res.decision == "exact" and res.best_match is not None and not (res.best_match.uncovered_capabilities or []):
                pending = res.best_match
            else:
                pending = None
            best_id = res.best_match.agent_id if res.best_match else None
            best_score = round(res.best_match.coverage_score, 2) if res.best_match else None
            rerouted = await route_domain(
                user_message=state["latest_user_message"],
                extracted_entities=state["extracted_entities"],
                conversation_history=state["messages"],
                agent_matches=res.matches,
                candidate_agents=enriched.agent_candidates,
            )
            pipeline_log(
                state["session_id"],
                "chain.agent_match",
                "evaluate_agent_match",
                decision=res.decision,
                candidates=len(enriched.agent_candidates or []),
                best_agent_id=best_id,
                best_coverage_score=best_score,
                pending_exact_redirect=pending is not None,
                inferred_domain=rerouted.primary.domain,
                inferred_sub_domain=rerouted.primary.sub_domain,
            )
            return {
                "enriched_context": enriched2,
                "agent_matches": res.matches,
                "agent_match_decision": res.decision,
                "pending_redirect_agent_match": pending,
                "pending_redirect": pending is not None,
                "domain": rerouted.primary,
                "domain_candidates": [a.model_dump() for a in rerouted.alternatives],
                "cross_domain_links": [l.model_dump() for l in rerouted.cross_domain_links],
            }

        def route_after_entry(state: AnalystState) -> str:
            if state.get("pending_redirect_agent_match"):
                pm = state.get("pending_redirect_agent_match")
                pipeline_log(
                    state["session_id"],
                    "orchestrator.route",
                    "after_receive_message",
                    next_node="handle_pending_redirect",
                    reason="pending_redirect_choice",
                    agent_id=getattr(pm, "agent_id", None),
                )
                return "handle_pending_redirect"
            pipeline_log(state["session_id"], "orchestrator.route", "after_receive_message", next_node="classify_intent", reason="full_pipeline")
            return "classify_intent"

        def route_after_agent_match(state: AnalystState) -> str:
            if state.get("agent_match_decision") == "exact" and state.get("pending_redirect_agent_match"):
                pipeline_log(
                    state["session_id"],
                    "orchestrator.route",
                    "after_evaluate_agent_match",
                    next_node="prepare_redirect_choice",
                    reason="exact_match_offer_redirect_or_build",
                )
                return "prepare_redirect_choice"
            pipeline_log(
                state["session_id"],
                "orchestrator.route",
                "after_evaluate_agent_match",
                next_node="evaluate_sufficiency",
                reason="partial_or_none",
                decision=state.get("agent_match_decision"),
            )
            return "evaluate_sufficiency"

        def route_after_sufficiency(state: AnalystState) -> str:
            score = state.get("sufficiency_score") or 0
            iteration = int(state.get("iteration") or 0)
            if score >= SUFFICIENCY_THRESHOLD:
                pipeline_log(
                    state["session_id"],
                    "orchestrator.route",
                    "after_evaluate_sufficiency",
                    next_node="synthesize_final",
                    score=score,
                    threshold=SUFFICIENCY_THRESHOLD,
                )
                return "synthesize_final"
            if iteration >= MAX_ITERATIONS:
                pipeline_log(
                    state["session_id"],
                    "orchestrator.route",
                    "after_evaluate_sufficiency",
                    next_node="force_finalize",
                    score=score,
                    iteration=iteration,
                    max_iterations=MAX_ITERATIONS,
                )
                return "force_finalize"
            pipeline_log(
                state["session_id"],
                "orchestrator.route",
                "after_evaluate_sufficiency",
                next_node="generate_clarification",
                score=score,
                iteration=iteration,
                gaps_preview=(state.get("gaps") or [])[:8],
            )
            return "generate_clarification"

        async def prepare_redirect_choice(state: AnalystState) -> dict[str, Any]:
            best = state.get("pending_redirect_agent_match")
            if not best:
                # На случай неожиданного состояния
                pipeline_log(state["session_id"], "orchestrator.node", "prepare_redirect_choice", outcome="aborted_no_best_match")
                return {"pending_redirect": False, "pending_redirect_agent_match": None, "agent_match_decision": "none"}

            # Сохраняем best match для следующего сообщения
            agent_name = best.agent_id
            # Пытаемся восстановить имя из enriched_context
            for a in state["enriched_context"].agent_candidates:
                if a.id == best.agent_id:
                    agent_name = a.name
                    break

            question = (
                f"В банке уже есть существующий агент `{agent_name}` (подходит по capabilities с score ~ {best.coverage_score:.0f}). "
                "Хотите:\n1) Получить доступ к существующему агенту (redirect)\n2) Всё равно строить/докомпозировать новый (build)?"
            )
            pipeline_log(
                state["session_id"],
                "orchestrator.node",
                "prepare_redirect_choice",
                outcome="await_user",
                agent_id=best.agent_id,
                agent_name=agent_name,
                coverage_score=round(best.coverage_score, 2),
            )
            return {
                "output": {"kind": "redirect_choice", "agent_id": best.agent_id, "agent_name": agent_name, "question": question},
            }

        async def evaluate_sufficiency_node(state: AnalystState) -> dict[str, Any]:
            domain = state["domain"]
            if domain is None:
                pipeline_log(state["session_id"], "chain.sufficiency", "evaluate_sufficiency", score=0, gaps=["missing_domain"], reason="no_domain")
                return {"sufficiency_score": 0, "gaps": ["missing_domain"]}

            covered_by_agents = []
            for m in state["agent_matches"]:
                # Для Sufficiency важно знать, какие capabilities потенциально закрыты агентами.
                # Поэтому не режем всё жестким порогом partial/none; берём все ненулевые перекрытия.
                if m.coverage_score > 0:
                    covered_by_agents.extend(m.covered_capabilities)
            covered_by_agents = sorted(set(covered_by_agents))

            intent = state["extracted_entities"].intent or IntentType.new_system
            dyn_requirements = await build_dynamic_requirements(
                extracted_entities=state["extracted_entities"],
                domain=domain,
                enriched_context=state["enriched_context"],
            )
            enriched = state["enriched_context"].model_copy(deep=True)
            enriched.domain_candidates = [DomainCandidate.model_validate(c) for c in state.get("domain_candidates", [])]
            enriched.cross_domain_links = [DomainLink.model_validate(c) for c in state.get("cross_domain_links", [])]
            if not state["agent_matches"] and state["extracted_entities"].capabilities:
                proposal = await propose_architecture(
                    extracted_entities=state["extracted_entities"],
                    domain=domain,
                    enriched_context=enriched,
                )
                enriched.architecture_proposal = proposal.model_dump()
            res = await evaluate_sufficiency(
                extracted_entities=state["extracted_entities"],
                enriched_context=enriched,
                intent=str(intent),
                domain=domain,
                covered_by_agents=covered_by_agents,
                dynamic_requirements=dyn_requirements,
            )

            # store to state
            pipeline_log(
                state["session_id"],
                "chain.sufficiency",
                "evaluate_sufficiency",
                score=res.score,
                threshold=SUFFICIENCY_THRESHOLD,
                gaps=res.gaps[:12] if res.gaps else [],
                gaps_count=len(res.gaps or []),
                dynamic_requirements=len(dyn_requirements),
                has_architecture_proposal=bool(enriched.architecture_proposal),
            )
            enriched.dynamic_requirements = dyn_requirements
            return {
                "sufficiency_score": res.score,
                "gaps": res.gaps,
                "dynamic_requirements": [r.model_dump() for r in dyn_requirements],
                "enriched_context": enriched,
            }

        async def generate_clarification_node(state: AnalystState) -> dict[str, Any]:
            gaps = state.get("gaps") or []
            already_asked = list(state.get("already_asked") or [])

            res = await generate_clarification(
                gaps=gaps,
                conversation_history=state["messages"],
                already_asked=already_asked,
                enriched_context=state["enriched_context"],
            )

            # iteration считается количеством итераций уточнения
            iteration = int(state.get("iteration") or 0) + 1
            already_asked2 = list(already_asked) + list(res.target_gaps or [])
            already_asked2 = sorted(set(already_asked2))

            pipeline_log(
                state["session_id"],
                "orchestrator.node",
                "generate_clarification",
                iteration=iteration,
                target_gaps=res.target_gaps,
                questions_count=len(res.questions[:3]),
                expected_impact=res.expected_impact,
            )
            return {
                "iteration": iteration,
                "already_asked": already_asked2,
                "output": {
                    "kind": "clarification",
                    "questions": res.questions[:3],
                    "target_gaps": res.target_gaps,
                    "expected_impact": res.expected_impact,
                },
            }

        async def synthesize_final_node(state: AnalystState) -> dict[str, Any]:
            domain = state.get("domain")
            if domain is None:
                pipeline_log(state["session_id"], "synthesis", "synthesize_final", outcome="error", error="missing_domain")
                return {"output": {"kind": "final", "error": "missing_domain"}}
            confidence = int(state.get("sufficiency_score") or SUFFICIENCY_THRESHOLD)
            req = synthesize_request(
                extracted_entities=state["extracted_entities"],
                domain=domain,
                enriched_context=state["enriched_context"],
                session_id=state["session_id"],
                iterations=int(state.get("iteration") or 0),
                confidence_score=confidence,
                unresolved_gaps=[],
                intent=str(state["extracted_entities"].intent or IntentType.new_system),
            )
            d = req.model_dump()
            pipeline_log(
                state["session_id"],
                "synthesis",
                "synthesize_final",
                outcome="ok",
                decision=str(getattr(req, "decision", None) or d.get("decision")),
                confidence_score=confidence,
                iterations=int(state.get("iteration") or 0),
            )
            return {"output": {"kind": "final", "concretized_request": d}}

        async def force_finalize_node(state: AnalystState) -> dict[str, Any]:
            domain = state.get("domain")
            if domain is None:
                pipeline_log(state["session_id"], "synthesis", "force_finalize", outcome="error", error="missing_domain")
                return {"output": {"kind": "final", "error": "missing_domain"}}
            confidence = int(state.get("sufficiency_score") or (SUFFICIENCY_THRESHOLD - 1))
            gaps = state.get("gaps") or []
            req = synthesize_request(
                extracted_entities=state["extracted_entities"],
                domain=domain,
                enriched_context=state["enriched_context"],
                session_id=state["session_id"],
                iterations=int(state.get("iteration") or 0),
                confidence_score=confidence,
                unresolved_gaps=gaps,
                intent=str(state["extracted_entities"].intent or IntentType.new_system),
            )
            fd = req.model_dump()
            pipeline_log(
                state["session_id"],
                "synthesis",
                "force_finalize",
                outcome="ok",
                decision=str(getattr(req, "decision", None) or fd.get("decision")),
                confidence_score=confidence,
                unresolved_gaps_count=len(gaps),
            )
            return {"output": {"kind": "final", "concretized_request": fd, "force_finalize": True}}

        def route_after_handle_pending_redirect(state: AnalystState) -> str:
            kind = (state.get("output") or {}).get("kind")
            nxt = "redirect" if kind == "redirect" else "evaluate_sufficiency"
            pipeline_log(
                state["session_id"],
                "orchestrator.route",
                "after_handle_pending_redirect",
                next_node=nxt,
                output_kind=kind,
            )
            return nxt

        # Nodes
        g.add_node("receive_message", receive_message)
        g.add_node("handle_pending_redirect", handle_pending_redirect)
        g.add_node("classify_intent", classify_intent_node)
        g.add_node("extract_entities", extract_entities_node)
        g.add_node("detect_domain", detect_domain_node)
        g.add_node("enrich_context", enrich_context_node)
        g.add_node("evaluate_agent_match", evaluate_agent_match_node)
        g.add_node("prepare_redirect_choice", prepare_redirect_choice)
        g.add_node("evaluate_sufficiency", evaluate_sufficiency_node)
        g.add_node("generate_clarification", generate_clarification_node)
        g.add_node("synthesize_final", synthesize_final_node)
        g.add_node("force_finalize", force_finalize_node)

        # Edges
        g.set_entry_point("receive_message")
        g.add_conditional_edges("receive_message", route_after_entry, {
            "handle_pending_redirect": "handle_pending_redirect",
            "classify_intent": "classify_intent",
        })

        g.add_edge("classify_intent", "extract_entities")
        g.add_edge("extract_entities", "detect_domain")
        g.add_edge("detect_domain", "enrich_context")
        g.add_edge("enrich_context", "evaluate_agent_match")
        g.add_conditional_edges("evaluate_agent_match", route_after_agent_match, {
            "prepare_redirect_choice": "prepare_redirect_choice",
            "evaluate_sufficiency": "evaluate_sufficiency",
        })

        g.add_conditional_edges(
            "handle_pending_redirect",
            route_after_handle_pending_redirect,
            {
                "redirect": END,
                "evaluate_sufficiency": "evaluate_sufficiency",
            },
        )

        g.add_conditional_edges("evaluate_sufficiency", route_after_sufficiency, {
            "synthesize_final": "synthesize_final",
            "force_finalize": "force_finalize",
            "generate_clarification": "generate_clarification",
        })

        g.add_edge("prepare_redirect_choice", END)
        g.add_edge("generate_clarification", END)
        g.add_edge("synthesize_final", END)
        g.add_edge("force_finalize", END)

        return g.compile()

    async def process_message(self, session_state: dict[str, Any], user_message: str) -> dict[str, Any]:
        # Normalize / hydrate state from session_state
        session_id = str(session_state.get("session_id") or "sess_unknown")
        messages = list(session_state.get("messages") or [])
        iteration = int(session_state.get("iteration") or 0)

        extracted_entities = session_state.get("extracted_entities") or ExtractedEntities()
        if isinstance(extracted_entities, dict):
            extracted_entities = ExtractedEntities.model_validate(extracted_entities)

        domain = session_state.get("domain")
        if isinstance(domain, dict):
            domain = DomainInfo.model_validate(domain)

        enriched_context = session_state.get("enriched_context") or EnrichedContext()
        if isinstance(enriched_context, dict):
            enriched_context = EnrichedContext.model_validate(enriched_context)

        agent_matches = session_state.get("agent_matches") or []
        normalized_agent_matches: list[AgentMatch] = []
        for m in agent_matches:
            if isinstance(m, AgentMatch):
                normalized_agent_matches.append(m)
            else:
                normalized_agent_matches.append(AgentMatch.model_validate(m))

        already_asked = list(session_state.get("already_asked") or [])

        pending_redirect_agent_match = session_state.get("pending_redirect_agent_match")
        if pending_redirect_agent_match is not None and isinstance(pending_redirect_agent_match, dict):
            pending_redirect_agent_match = AgentMatch.model_validate(pending_redirect_agent_match)

        initial_state: AnalystState = {
            "session_id": session_id,
            "latest_user_message": user_message,
            "messages": messages,
            "iteration": iteration,
            "extracted_entities": extracted_entities,
            "domain": domain,
            "enriched_context": enriched_context,
            "agent_matches": normalized_agent_matches,
            "snippet_matches": enriched_context.snippet_matches if hasattr(enriched_context, "snippet_matches") else [],
            "sufficiency_score": session_state.get("sufficiency_score"),
            "gaps": list(session_state.get("gaps") or []),
            "already_asked": already_asked,
            "pending_redirect_agent_match": pending_redirect_agent_match,
            "pending_redirect": pending_redirect_agent_match is not None,
            "domain_candidates": list(session_state.get("domain_candidates") or []),
            "cross_domain_links": list(session_state.get("cross_domain_links") or []),
            "dynamic_requirements": list(session_state.get("dynamic_requirements") or []),
        }

        pipeline_log(
            session_id,
            "orchestrator",
            "process_message_start",
            iteration=iteration,
            pending_exact_redirect_choice=pending_redirect_agent_match is not None,
            message_preview=(user_message or "")[:200],
            graph="langgraph" if self._graph is not None else "procedural",
        )

        if self._graph is not None:
            out_state: dict[str, Any] = await self._graph.ainvoke(initial_state)
        else:
            # Procedural fallback: не используем langgraph, но сохраняем ту же семантику переходов.
            pipeline_log(session_id, "orchestrator", "procedural_fallback", reason="langgraph_not_installed")
            state = initial_state

            # receive_message
            state["messages"] = list(state["messages"]) + [{"role": "user", "text": state["latest_user_message"]}]
            pipeline_log(session_id, "orchestrator.node", "receive_message", history_len=len(state["messages"]) - 1, procedural=True)

            # Exact-match redirect choice handling (pending flag)
            if state.get("pending_redirect_agent_match"):
                agent_match = state.get("pending_redirect_agent_match")
                latest = (state.get("latest_user_message") or "").lower()
                wants_redirect = any(
                    k in latest
                    for k in [
                        "redirect",
                        "перенаправ",
                        "дать доступ",
                        "получить доступ",
                        "использовать существующий",
                    ]
                )

                if agent_match and wants_redirect:
                    redirect_response = build_redirect_response(state["enriched_context"], agent_match)
                    state["pending_redirect"] = False
                    state["pending_redirect_agent_match"] = None
                    state["output"] = {"kind": "redirect", "redirect_response": redirect_response.model_dump()}
                    pipeline_log(session_id, "orchestrator.route", "procedural_pending_redirect", outcome="redirect", agent_id=agent_match.agent_id)
                else:
                    # build path: downgrade and continue to sufficiency without recomputing enrichment
                    state["pending_redirect"] = False
                    state["pending_redirect_agent_match"] = None
                    pipeline_log(session_id, "orchestrator.route", "procedural_pending_redirect", outcome="build_continue_sufficiency")

                    # evaluate_sufficiency
                    domain = state.get("domain")
                    if domain is None:
                        state["sufficiency_score"] = 0
                        state["gaps"] = ["missing_domain"]
                    else:
                        covered_by_agents: list[str] = []
                        for m in state["agent_matches"]:
                            if m.coverage_score > 0:
                                covered_by_agents.extend(m.covered_capabilities)
                        covered_by_agents = sorted(set(covered_by_agents))

                        intent = state["extracted_entities"].intent or IntentType.new_system
                        if not state["agent_matches"] and state["extracted_entities"].capabilities:
                            proposal = await propose_architecture(
                                extracted_entities=state["extracted_entities"],
                                domain=domain,
                                enriched_context=state["enriched_context"],
                            )
                            state["enriched_context"].architecture_proposal = proposal.model_dump()
                        res = await evaluate_sufficiency(
                            extracted_entities=state["extracted_entities"],
                            enriched_context=state["enriched_context"],
                            intent=str(intent),
                            domain=domain,
                            covered_by_agents=covered_by_agents,
                            dynamic_requirements=await build_dynamic_requirements(
                                extracted_entities=state["extracted_entities"],
                                domain=domain,
                                enriched_context=state["enriched_context"],
                            ),
                        )
                        state["sufficiency_score"] = res.score
                        state["gaps"] = res.gaps

                    # route_after_sufficiency
                    score = state.get("sufficiency_score") or 0
                    iteration = int(state.get("iteration") or 0)
                    if score >= SUFFICIENCY_THRESHOLD:
                        req = synthesize_request(
                            extracted_entities=state["extracted_entities"],
                            domain=state["domain"],
                            enriched_context=state["enriched_context"],
                            session_id=state["session_id"],
                            iterations=iteration,
                            confidence_score=int(score),
                            unresolved_gaps=[],
                            intent=str(state["extracted_entities"].intent or IntentType.new_system),
                        )
                        state["output"] = {"kind": "final", "concretized_request": req.model_dump()}
                    elif iteration >= MAX_ITERATIONS:
                        gaps = state.get("gaps") or []
                        req = synthesize_request(
                            extracted_entities=state["extracted_entities"],
                            domain=state["domain"],
                            enriched_context=state["enriched_context"],
                            session_id=state["session_id"],
                            iterations=iteration,
                            confidence_score=max(0, int(score)),
                            unresolved_gaps=gaps,
                            intent=str(state["extracted_entities"].intent or IntentType.new_system),
                        )
                        state["output"] = {"kind": "final", "concretized_request": req.model_dump(), "force_finalize": True}
                    else:
                        res_clar = await generate_clarification(
                            gaps=state.get("gaps") or [],
                            conversation_history=state["messages"],
                            already_asked=state.get("already_asked") or [],
                            enriched_context=state["enriched_context"],
                        )
                        state["iteration"] = iteration + 1
                        already_asked = list(state.get("already_asked") or []) + list(res_clar.target_gaps or [])
                        state["already_asked"] = sorted(set(already_asked))
                        state["output"] = {
                            "kind": "clarification",
                            "questions": res_clar.questions[:3],
                            "target_gaps": res_clar.target_gaps,
                            "expected_impact": res_clar.expected_impact,
                        }

                out_state = state
            else:
                # Normal flow: re-run pipeline
                pipeline_log(session_id, "orchestrator.route", "procedural", branch="full_pipeline")
                res_intent = await classify_intent(user_message=state["latest_user_message"], conversation_history=state["messages"])
                pipeline_log(
                    session_id,
                    "chain.intent",
                    "classify_intent",
                    intent=str(res_intent.intent),
                    confidence=round(res_intent.confidence, 4),
                    procedural=True,
                )
                state["extracted_entities"] = state["extracted_entities"].model_copy(update={"intent": res_intent.intent})

                res_entities = await extract_entities(
                    user_message=state["latest_user_message"],
                    conversation_history=state["messages"],
                    existing_entities=state["extracted_entities"],
                    domain_hint=None,
                )
                merge_strategy = res_entities.merge_strategy
                if merge_strategy == "overwrite" and not (res_entities.entities.capabilities or []):
                    merge_strategy = "append"
                state["extracted_entities"] = _merge_entities(state["extracted_entities"], res_entities.entities, merge_strategy)

                routed = await route_domain(
                    user_message=state["latest_user_message"],
                    extracted_entities=state["extracted_entities"],
                    conversation_history=state["messages"],
                )
                state["domain"] = routed.primary
                state["domain_candidates"] = [a.model_dump() for a in routed.alternatives]
                state["cross_domain_links"] = [l.model_dump() for l in routed.cross_domain_links]
                dinfo = state["domain"]
                if dinfo is not None:
                    pipeline_log(
                        session_id,
                        "chain.domain",
                        "detect_domain",
                        domain=dinfo.domain,
                        sub_domain=dinfo.sub_domain,
                        procedural=True,
                    )

                state["enriched_context"] = await self._enricher.enrich_context(
                    state["domain"],  # type: ignore[arg-type]
                    state["extracted_entities"],
                    session_id=session_id,
                )
                state["agent_matches"] = state["enriched_context"].agent_matches or []

                agent_match_res = await evaluate_agent_match(
                    extracted_entities=state["extracted_entities"],
                    candidate_agents=state["enriched_context"].agent_candidates,
                )
                # обновляем matches в enriched_context
                state["enriched_context"].agent_matches = agent_match_res.matches
                state["agent_matches"] = agent_match_res.matches
                state["agent_match_decision"] = agent_match_res.decision
                rerouted = await route_domain(
                    user_message=state["latest_user_message"],
                    extracted_entities=state["extracted_entities"],
                    conversation_history=state["messages"],
                    agent_matches=agent_match_res.matches,
                    candidate_agents=state["enriched_context"].agent_candidates,
                )
                state["domain"] = rerouted.primary
                state["domain_candidates"] = [a.model_dump() for a in rerouted.alternatives]
                state["cross_domain_links"] = [l.model_dump() for l in rerouted.cross_domain_links]
                # Procedural redirect_choice: only if best agent covers all required capabilities.
                if (
                    agent_match_res.decision == "exact"
                    and agent_match_res.best_match is not None
                    and not (agent_match_res.best_match.uncovered_capabilities or [])
                ):
                    state["pending_redirect_agent_match"] = agent_match_res.best_match
                else:
                    state["pending_redirect_agent_match"] = None

                if agent_match_res.decision == "exact" and state.get("pending_redirect_agent_match"):
                    best = state["pending_redirect_agent_match"]
                    agent_name = best.agent_id
                    for a in state["enriched_context"].agent_candidates:
                        if a.id == best.agent_id:
                            agent_name = a.name
                            break
                    question = (
                        f"В банке уже есть существующий агент `{agent_name}` (подходит по capabilities с score ~ {best.coverage_score:.0f}). "
                        "Хотите:\n1) Получить доступ к существующему агенту (redirect)\n2) Всё равно строить/докомпозировать новый (build)?"
                    )
                    state["output"] = {"kind": "redirect_choice", "agent_id": best.agent_id, "agent_name": agent_name, "question": question}
                    out_state = state
                else:
                    # evaluate_sufficiency
                    domain = state.get("domain")
                    covered_by_agents: list[str] = []
                    for m in state["agent_matches"]:
                        if m.coverage_score > 0:
                            covered_by_agents.extend(m.covered_capabilities)
                    covered_by_agents = sorted(set(covered_by_agents))

                    intent = state["extracted_entities"].intent or IntentType.new_system
                    if not state["agent_matches"] and state["extracted_entities"].capabilities:
                        proposal = await propose_architecture(
                            extracted_entities=state["extracted_entities"],
                            domain=domain,  # type: ignore[arg-type]
                            enriched_context=state["enriched_context"],
                        )
                        state["enriched_context"].architecture_proposal = proposal.model_dump()
                    res = await evaluate_sufficiency(
                        extracted_entities=state["extracted_entities"],
                        enriched_context=state["enriched_context"],
                        intent=str(intent),
                        domain=domain,  # type: ignore[arg-type]
                        covered_by_agents=covered_by_agents,
                        dynamic_requirements=await build_dynamic_requirements(
                            extracted_entities=state["extracted_entities"],
                            domain=domain,  # type: ignore[arg-type]
                            enriched_context=state["enriched_context"],
                        ),
                    )
                    state["sufficiency_score"] = res.score
                    state["gaps"] = res.gaps

                    score = res.score
                    iteration = int(state.get("iteration") or 0)
                    if score >= SUFFICIENCY_THRESHOLD:
                        req = synthesize_request(
                            extracted_entities=state["extracted_entities"],
                            domain=state["domain"],  # type: ignore[arg-type]
                            enriched_context=state["enriched_context"],
                            session_id=state["session_id"],
                            iterations=iteration,
                            confidence_score=int(score),
                            unresolved_gaps=[],
                            intent=str(state["extracted_entities"].intent or IntentType.new_system),
                        )
                        state["output"] = {"kind": "final", "concretized_request": req.model_dump()}
                    elif iteration >= MAX_ITERATIONS:
                        req = synthesize_request(
                            extracted_entities=state["extracted_entities"],
                            domain=state["domain"],  # type: ignore[arg-type]
                            enriched_context=state["enriched_context"],
                            session_id=state["session_id"],
                            iterations=iteration,
                            confidence_score=max(0, int(score)),
                            unresolved_gaps=state.get("gaps") or [],
                            intent=str(state["extracted_entities"].intent or IntentType.new_system),
                        )
                        state["output"] = {"kind": "final", "concretized_request": req.model_dump(), "force_finalize": True}
                    else:
                        res_clar = await generate_clarification(
                            gaps=state.get("gaps") or [],
                            conversation_history=state["messages"],
                            already_asked=state.get("already_asked") or [],
                            enriched_context=state["enriched_context"],
                        )
                        state["iteration"] = iteration + 1
                        already_asked = list(state.get("already_asked") or []) + list(res_clar.target_gaps or [])
                        state["already_asked"] = sorted(set(already_asked))
                        state["output"] = {
                            "kind": "clarification",
                            "questions": res_clar.questions[:3],
                            "target_gaps": res_clar.target_gaps,
                            "expected_impact": res_clar.expected_impact,
                        }
                    out_state = state

        # Persist updated fields back to session_state
        for k, v in out_state.items():
            if k == "output":
                continue
            session_state[k] = v
        output = out_state.get("output") or {"kind": "final", "concretized_request": None}
        pipeline_log(
            session_id,
            "orchestrator",
            "process_message_end",
            kind=output.get("kind"),
            iteration=out_state.get("iteration", iteration),
            sufficiency_score=out_state.get("sufficiency_score"),
            agent_match_decision=out_state.get("agent_match_decision"),
        )
        return output

