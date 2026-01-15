"""
Knowledge Tools Module

Tools for searching knowledge base, finding similar incidents,
getting runbooks, and retrieving proven solutions.

These tools are read-only and safe for any mode that needs
to access organizational knowledge.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.agentic.tools import Tool, ToolParameter, ToolModule

logger = logging.getLogger(__name__)


class KnowledgeTools(ToolModule):
    """
    Knowledge-related tools for accessing organizational documentation,
    past incidents, runbooks, and proven solutions.
    
    These tools are safe for use in any mode (Inquiry, Troubleshooting)
    as they are read-only information gathering tools.
    """
    
    def _register_tools(self):
        """Register all knowledge tools"""
        
        # 1. Search Knowledge Base
        self._register_tool(
            Tool(
                name="search_knowledge",
                description="Search the knowledge base for runbooks, SOPs, architecture docs, troubleshooting guides, and postmortems. Use this to find documented procedures and past solutions.",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query - describe what you're looking for",
                        required=True
                    ),
                    ToolParameter(
                        name="doc_type",
                        type="string",
                        description="Filter by document type",
                        required=False,
                        enum=["runbook", "sop", "architecture", "troubleshooting", "postmortem", "design_doc"]
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of results (default 5)",
                        required=False,
                        default=5
                    )
                ]
            ),
            self._search_knowledge
        )

        # 2. Get Similar Incidents
        self._register_tool(
            Tool(
                name="get_similar_incidents",
                description="Find past incidents similar to the current alert using vector similarity. Returns past incidents with their resolutions and what worked.",
                parameters=[
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of similar incidents to return (default 3)",
                        required=False,
                        default=3
                    )
                ]
            ),
            self._get_similar_incidents
        )

        # 3. Get Runbook
        self._register_tool(
            Tool(
                name="get_runbook",
                description="Get a specific runbook for a service or alert type. Returns step-by-step remediation procedures.",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Service name to find runbook for",
                        required=False
                    ),
                    ToolParameter(
                        name="alert_type",
                        type="string",
                        description="Alert type/name to find runbook for",
                        required=False
                    )
                ]
            ),
            self._get_runbook
        )

        # 4. Get Proven Solutions (Learning System)
        self._register_tool(
            Tool(
                name="get_proven_solutions",
                description="Find solutions that WORKED for similar problems in the past. Returns commands, runbooks, or knowledge docs that successfully resolved similar issues. Use this before suggesting new solutions to check if we've solved this before.",
                parameters=[
                    ToolParameter(
                        name="problem_description",
                        type="string",
                        description="Description of the current problem to find similar past solutions",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of solutions to return (default 5)",
                        required=False,
                        default=5
                    )
                ]
            ),
            self._get_proven_solutions
        )

    # ========== Tool Implementations ==========

    async def _search_knowledge(self, args: Dict[str, Any]) -> str:
        """Search knowledge base"""
        from app.services.knowledge_search_service import KnowledgeSearchService

        query = args.get("query", "")
        doc_type = args.get("doc_type")
        limit = args.get("limit", 5)

        if not query:
            return "Error: query parameter is required"

        try:
            service = KnowledgeSearchService(self.db)
            doc_types = [doc_type] if doc_type else None
            results = service.search_similar(
                query=query,
                doc_types=doc_types,
                limit=limit,
                min_similarity=0.3
            )

            if not results:
                return f"No knowledge base documents found matching '{query}'"

            output = [f"Found {len(results)} relevant documents:\n"]
            for i, result in enumerate(results, 1):
                title = result.get('source_title', 'Untitled')
                doc_type = result.get('doc_type', 'unknown')
                similarity = result.get('similarity', 0)
                content = result.get('content', '')[:500]  # Truncate
                view_url = result.get('view_url')
                source_url = result.get('source_url')

                output.append(f"{i}. **{title}** (type: {doc_type}, relevance: {similarity:.2f})")
                if view_url:
                    output.append(f"   View: [Open runbook]({view_url})")
                elif source_url:
                    output.append(f"   Source: {source_url}")
                output.append(f"   {content}...")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Knowledge search error: {e}")
            return f"Error searching knowledge base: {str(e)}"

    async def _get_similar_incidents(self, args: Dict[str, Any]) -> str:
        """Get similar past incidents"""
        from app.services.similarity_service import SimilarityService

        if not self.alert_id:
            return "No alert context available - cannot find similar incidents"

        limit = args.get("limit", 3)

        try:
            service = SimilarityService(self.db)
            result = service.find_similar_alerts(self.alert_id, limit=limit)

            if not result or not result.similar_incidents:
                return "No similar past incidents found"

            output = [f"Found {len(result.similar_incidents)} similar past incidents:\n"]
            for i, incident in enumerate(result.similar_incidents, 1):
                output.append(f"{i}. **{incident.alert_name}**")
                output.append(f"   - Similarity: {incident.similarity_score:.2%}")
                output.append(f"   - Severity: {incident.severity}")
                output.append(f"   - Instance: {incident.instance}")
                output.append(f"   - Occurred: {incident.occurred_at}")

                if incident.resolution:
                    res = incident.resolution
                    output.append(f"   - Resolution: {res.method}")
                    if res.runbook_name:
                        output.append(f"   - Runbook used: {res.runbook_name}")
                    if res.time_minutes:
                        output.append(f"   - Time to resolve: {res.time_minutes} minutes")
                    output.append(f"   - Success: {'Yes' if res.success else 'No'}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Similar incidents error: {e}")
            return f"Error finding similar incidents: {str(e)}"

    async def _get_runbook(self, args: Dict[str, Any]) -> str:
        """Get runbook for service/alert type"""
        from app.models_remediation import Runbook, RunbookStep
        from sqlalchemy.orm import selectinload

        service = args.get("service")
        alert_type = args.get("alert_type")

        if not service and not alert_type:
            return "Error: Either service or alert_type parameter is required"

        try:
            query = self.db.query(Runbook).options(
                selectinload(Runbook.steps)
            ).filter(Runbook.enabled == True)

            # Search by service name in name/description/tags
            if service:
                query = query.filter(
                    Runbook.name.ilike(f"%{service}%") |
                    Runbook.description.ilike(f"%{service}%")
                )

            # Search by alert_type in name/description  
            if alert_type:
                query = query.filter(
                    Runbook.name.ilike(f"%{alert_type}%") |
                    Runbook.description.ilike(f"%{alert_type}%")
                )

            runbooks = query.limit(3).all()

            if not runbooks:
                return f"No runbooks found for service='{service}' or alert_type='{alert_type}'"

            output = [f"Found {len(runbooks)} relevant runbooks:\n"]
            for runbook in runbooks:
                output.append(f"## {runbook.name}")
                output.append(f"Description: {runbook.description or 'No description'}")
                output.append(f"Category: {runbook.category or 'Uncategorized'}")
                output.append(f"Auto-execute: {'Yes' if runbook.auto_execute else 'No'}")
                output.append(f"View: [Open runbook](/runbooks/{runbook.id}/view)")
                output.append("\n**Steps:**")

                # Get steps using relationship (already loaded via selectinload)
                sorted_steps = sorted(runbook.steps, key=lambda s: s.step_order)

                for step in sorted_steps:
                    output.append(f"\n{step.step_order}. **{step.name}**")
                    if step.description:
                        output.append(f"   {step.description}")
                    if step.command_linux:
                        output.append(f"   Linux: `{step.command_linux[:100]}`")
                    if step.command_windows:
                        output.append(f"   Windows: `{step.command_windows[:100]}`")

                output.append("\n---\n")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Runbook fetch error: {e}")
            return f"Error fetching runbooks: {str(e)}"

    async def _get_proven_solutions(self, args: Dict[str, Any]) -> str:
        """Find solutions that worked for similar problems in the past."""
        import sqlalchemy as sa
        from sqlalchemy import func
        
        problem_description = args.get("problem_description", "").strip()
        limit = args.get("limit", 5)

        if not problem_description:
            return "Error: problem_description is required"

        try:
            from app.models import SolutionOutcome
            
            # Query for successful solutions
            results = (
                self.db.query(
                    SolutionOutcome.solution_type,
                    SolutionOutcome.solution_reference,
                    SolutionOutcome.solution_summary,
                    SolutionOutcome.problem_description,
                    func.count().label('total_uses'),
                    func.sum(func.cast(SolutionOutcome.success == True, type_=sa.Integer)).label('success_count')
                )
                .filter(SolutionOutcome.success == True)
                .group_by(
                    SolutionOutcome.solution_type,
                    SolutionOutcome.solution_reference,
                    SolutionOutcome.solution_summary,
                    SolutionOutcome.problem_description
                )
                .order_by(func.count().desc())
                .limit(limit)
                .all()
            )

            if not results:
                return "No proven solutions found in the learning database yet. This is a new problem - proceed with your own analysis."

            output_parts = ["**Proven Solutions from Past Success:**\n"]
            for i, r in enumerate(results, 1):
                output_parts.append(
                    f"{i}. **{r.solution_type.title()}**: `{r.solution_reference[:100] if r.solution_reference else 'N/A'}`\n"
                    f"   - Original problem: {r.problem_description[:100] if r.problem_description else 'N/A'}...\n"
                    f"   - Used {r.total_uses} time(s), all successful\n"
                )

            output_parts.append("\n*These solutions worked before - consider trying them first.*")
            return "\n".join(output_parts)

        except Exception as e:
            logger.error(f"Error in get_proven_solutions: {e}")
            return f"Error searching proven solutions: {str(e)}"
