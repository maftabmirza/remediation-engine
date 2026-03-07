## Plan: Incident-First Postmortems

Make postmortems an incident-level capability instead of an alert-only feature. The recommended approach is a hybrid incident model: build a native incident aggregate from existing alert correlations and clusters, optionally link it to ITSM incidents, and generate one high-quality postmortem per resolved incident using all available evidence: alerts, executions, feedback, troubleshooting history, observability data, change events, knowledge/design docs, and dependency topology.

**Steps**
1. Define a native incident source of truth.
   Recommendation: use `AlertCorrelation` as the primary grouping seed, fall back to `AlertCluster`, and optionally link `IncidentEvent` when present. This is the blocking design decision for the rest.
2. Define incident resolution eligibility.
   Require a stable resolved state before generation, so postmortems are not created for flapping incidents.
3. Add incident-scoped data modeling.
   Introduce an `Incident` aggregate plus linkage to alerts, clusters, correlations, change events, and postmortems. Keep `alert_id` on postmortems for backward compatibility, but make `incident_id` the new primary anchor.
4. Build incident assembly and evidence collection.
   Create one service that materializes a resolved incident and another that gathers all evidence for that incident: alert timeline, `RunbookExecution` and step outputs, `IncidentMetrics`, `AnalysisFeedback`, `ExecutionOutcome`, `SolutionOutcome`, `AgentSession` and `AgentStep`, `ChangeEvent`, `ChangeImpactAnalysis`, similar incidents, dependency context, and knowledge sources.
5. Add observability enrichment in parallel once the incident window contract is defined.
   Summarize Prometheus, Loki, and Tempo evidence into postmortem-safe inputs instead of feeding raw metrics/logs/traces directly.
6. Add knowledge and topology enrichment in parallel with observability enrichment.
   Pull relevant design documents, diagrams, architecture chunks, dependency paths, impacted components, and service health context into the evidence bundle.
7. Redesign generation around `incident_id`.
   Replace the current `generate(alert_id)` as the main flow with `generate(incident_id)`, while retaining an alert compatibility path that resolves or creates an incident first.
8. Separate deterministic sections from AI-generated sections.
   Deterministic: timeline, metrics, responders, remediation actions, affected services, linked changes, evidence references.
   AI-generated: impact summary, root cause synthesis, contributing factors, lessons learned, action items.
9. Add generation workflows.
   First: single high-quality postmortem for one resolved incident.
   Second: backlog generation for all eligible resolved incidents in a date range.
10. Expand the API and review workflow.
   Add endpoints to list eligible incidents, preview evidence, generate by incident, regenerate selected sections, attach out-of-band context, publish, and export.
11. Rebuild the UI as incident-first.
   Replace the alert-only generate modal with a resolved-incident picker and incident evidence preview. Add structured views for timeline, metrics, troubleshooting history, changes, logs/traces summaries, dependencies, and knowledge references.
12. Add export and distribution.
   Reuse the existing PDF service to export published postmortems and optionally attach them to external systems.
13. Add automated generation triggers.
   Generate when an incident reaches a stable resolved state, with debounce/grace-period controls and feature flags.
14. Backfill and migration.
   Map existing alert-linked postmortems to incident-linked records where possible and backfill recent resolved incidents for immediate usability.
15. Test and roll out behind a feature flag.
   Validate on recent real incidents before making incident-first postmortems the default.

**Relevant files**
- [app/services/postmortem_service.py](app/services/postmortem_service.py) — current alert-first generation flow to evolve.
- [app/routers/postmortem_api.py](app/routers/postmortem_api.py) — current postmortem endpoints to extend.
- [app/models_postmortem.py](app/models_postmortem.py) — add incident linkage and provenance metadata.
- [app/schemas_postmortem.py](app/schemas_postmortem.py) — add incident-based request/response contracts and evidence preview shapes.
- [app/models.py](app/models.py) — reuse `Alert`, `AlertCluster`, `IncidentMetrics`, and `SolutionOutcome`.
- [app/models_troubleshooting.py](app/models_troubleshooting.py) — reuse `AlertCorrelation` and troubleshooting patterns.
- [app/models_agent.py](app/models_agent.py) — reuse `AgentSession` and `AgentStep` for troubleshooting history.
- [app/models_learning.py](app/models_learning.py) — reuse `AnalysisFeedback` and `ExecutionOutcome`.
- [app/models_remediation.py](app/models_remediation.py) — reuse runbook execution evidence.
- [app/models_itsm.py](app/models_itsm.py) — reuse `IncidentEvent`, `ChangeEvent`, and `ChangeImpactAnalysis`.
- [app/models_knowledge.py](app/models_knowledge.py) — reuse design docs, chunks, and images.
- [app/models_application.py](app/models_application.py) — reuse application, component, and dependency context.
- [app/services/correlation_service.py](app/services/correlation_service.py) — strongest native incident-grouping reuse point.
- [app/services/effectiveness_service.py](app/services/effectiveness_service.py) — reuse feedback aggregation patterns.
- [app/services/change_impact_service.py](app/services/change_impact_service.py) — reuse change correlation logic.
- [app/services/service_health_service.py](app/services/service_health_service.py) — reuse health and topology context.
- [app/services/knowledge_search_service.py](app/services/knowledge_search_service.py) — reuse semantic knowledge retrieval.
- [app/services/prometheus_service.py](app/services/prometheus_service.py) — metrics evidence.
- [app/services/loki_client.py](app/services/loki_client.py) — logs evidence.
- [app/services/tempo_client.py](app/services/tempo_client.py) — trace evidence.
- [app/services/observability_orchestrator.py](app/services/observability_orchestrator.py) — coordinated multi-source evidence gathering.
- [app/services/agentic/context_enricher.py](app/services/agentic/context_enricher.py) — reuse context assembly patterns.
- [templates/postmortems.html](templates/postmortems.html) — rebuild into incident-first workflow.
- [app/services/pdf_service.py](app/services/pdf_service.py) — reuse for export.
- [schema/schema.sql](schema/schema.sql) — canonical schema updates.
- [atlas/migrations/](atlas/migrations/) — Atlas migrations for incident/postmortem schema changes.

**Verification**
1. Unit test incident assembly: correlation grouping, cluster fallback, resolved-state eligibility, grace-period handling, ITSM linkage.
2. Unit test evidence collection: timeline merge, metrics extraction, remediation aggregation, troubleshooting history, change correlation, knowledge retrieval, dependency context, observability summaries.
3. Unit test incident-first generation: generate from incident, alert compatibility path, regenerate preservation, deterministic section rebuilds, LLM fallback behavior.
4. Integration test APIs: eligible incident listing, evidence preview, generate, update, regenerate, publish, delete, export, auth boundaries.
5. E2E test the incident-first UI: pick resolved incident, preview evidence, generate, edit, regenerate, publish, export.
6. Validate Atlas flow: schema, migration, model, and schema contract stay aligned.
7. Manually review at least 10 recent resolved incidents and compare output quality against the current alert-only behavior.

**Decisions**
- Source of truth: hybrid, but native incident aggregation should be first-class.
- First release priority: quality over bulk throughput.
- Primary anchor: `incident_id`; keep `alert_id` only for compatibility and lineage.
- LLM role: synthesize narrative, not reconstruct facts.
- Included in scope: resolved incidents, resolved alerts, troubleshooting history, monitoring data, code/design knowledge, dependency context, and export planning.
- Excluded from first release: full cross-incident causality graphs, large-scale autonomous backfill, and executive dashboarding.

I saved this as the session plan. If you want, the next planning pass can turn this into a phase-by-phase implementation backlog with estimated effort per phase.
