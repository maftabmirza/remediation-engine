"""Application Service

Business logic for application registry operations.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import fnmatch

from app.models_application import Application, ApplicationComponent, ComponentDependency
from app.models import Alert


class ApplicationService:
    """Service layer for application registry operations."""

    def __init__(self, db: Session):
        self.db = db

    def match_alert_to_application(self, alert: Alert) -> Optional[Application]:
        """
        Match an alert to an application based on label matchers.
        
        Args:
            alert: Alert object with labels_json
            
        Returns:
            Matched Application or None
        """
        if not alert.labels_json:
            return None

        # Get all applications with matchers
        applications = self.db.query(Application).filter(
            Application.alert_label_matchers.isnot(None)
        ).all()

        for app in applications:
            if self._labels_match(alert.labels_json, app.alert_label_matchers):
                return app

        return None

    def match_alert_to_component(self, alert: Alert, app_id: Optional[UUID] = None) -> Optional[ApplicationComponent]:
        """
        Match an alert to a specific component.
        
        Args:
            alert: Alert object with labels
            app_id: Optional application ID to restrict search
            
        Returns:
            Matched ApplicationComponent or None
        """
        if not alert.labels_json:
            return None

        query = self.db.query(ApplicationComponent).filter(
            ApplicationComponent.alert_label_matchers.isnot(None)
        )

        if app_id:
            query = query.filter(ApplicationComponent.app_id == app_id)

        components = query.all()

        for component in components:
            if self._labels_match(alert.labels_json, component.alert_label_matchers):
                return component

        return None

    def _labels_match(self, alert_labels: Dict[str, str], matchers: Dict[str, str]) -> bool:
        """
        Check if alert labels match the specified patterns.
        
        Args:
            alert_labels: Alert labels dict
            matchers: Label patterns dict (supports wildcards)
            
        Returns:
            True if all matchers match
        """
        if not matchers:
            return False

        for key, pattern in matchers.items():
            alert_value = alert_labels.get(key)
            if not alert_value:
                return False

            # Support wildcard matching
            if not fnmatch.fnmatch(alert_value, pattern):
                return False

        return True

    def get_component_dependencies(
        self,
        component_id: UUID,
        include_upstream: bool = True,
        include_downstream: bool = True
    ) -> Dict[str, List[ApplicationComponent]]:
        """
        Get components that this component depends on (upstream) 
        and components that depend on this (downstream).
        
        Args:
            component_id: Component UUID
            include_upstream: Include upstream dependencies
            include_downstream: Include downstream dependencies
            
        Returns:
            Dict with 'upstream' and 'downstream' lists
        """
        result = {"upstream": [], "downstream": []}

        if include_upstream:
            # Components this component depends ON (outgoing edges)
            upstream = self.db.query(ApplicationComponent).join(
                ComponentDependency,
                ComponentDependency.to_component_id == ApplicationComponent.id
            ).filter(
                ComponentDependency.from_component_id == component_id
            ).all()
            result["upstream"] = upstream

        if include_downstream:
            # Components that depend ON this component (incoming edges)
            downstream = self.db.query(ApplicationComponent).join(
                ComponentDependency,
                ComponentDependency.from_component_id == ApplicationComponent.id
            ).filter(
                ComponentDependency.to_component_id == component_id
            ).all()
            result["downstream"] = downstream

        return result

    def find_upstream_components(self, component_id: UUID, max_depth: int = 5) -> List[ApplicationComponent]:
        """
        Recursively find all upstream dependencies.
        
        Args:
            component_id: Starting component
            max_depth: Maximum traversal depth
            
        Returns:
            List of upstream components
        """
        visited = set()
        result = []

        def traverse(comp_id: UUID, depth: int):
            if depth > max_depth or comp_id in visited:
                return
            
            visited.add(comp_id)
            deps = self.get_component_dependencies(comp_id, include_upstream=True, include_downstream=False)
            
            for upstream_comp in deps["upstream"]:
                if upstream_comp.id not in visited:
                    result.append(upstream_comp)
                    traverse(upstream_comp.id, depth + 1)

        traverse(component_id, 0)
        return result

    def find_downstream_components(self, component_id: UUID, max_depth: int = 5) -> List[ApplicationComponent]:
        """
        Recursively find all downstream dependents.
        
        Args:
            component_id: Starting component
            max_depth: Maximum traversal depth
            
        Returns:
            List of downstream components
        """
        visited = set()
        result = []

        def traverse(comp_id: UUID, depth: int):
            if depth > max_depth or comp_id in visited:
                return
            
            visited.add(comp_id)
            deps = self.get_component_dependencies(comp_id, include_upstream=False, include_downstream=True)
            
            for downstream_comp in deps["downstream"]:
                if downstream_comp.id not in visited:
                    result.append(downstream_comp)
                    traverse(downstream_comp.id, depth + 1)

        traverse(component_id, 0)
        return result

    def build_dependency_graph(self, app_id: UUID) -> Dict[str, Any]:
        """
        Build complete dependency graph for an application.
        
        Args:
            app_id: Application UUID
            
        Returns:
            Dict with 'nodes' and 'edges' for graph visualization
        """
        components = self.db.query(ApplicationComponent).filter(
            ApplicationComponent.app_id == app_id
        ).all()

        dependencies = self.db.query(ComponentDependency).join(
            ApplicationComponent,
            ComponentDependency.from_component_id == ApplicationComponent.id
        ).filter(
            ApplicationComponent.app_id == app_id
        ).all()

        nodes = [
            {
                "id": str(comp.id),
                "name": comp.name,
                "type": comp.component_type or "unknown",
                "criticality": comp.criticality,
                "app_id": str(comp.app_id)
            }
            for comp in components
        ]

        edges = [
            {
                "id": str(dep.id),
                "from": str(dep.from_component_id),
                "to": str(dep.to_component_id),
                "type": dep.dependency_type
            }
            for dep in dependencies
        ]

        return {"nodes": nodes, "edges": edges}
