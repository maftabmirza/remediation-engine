"""
Alert Clustering Service

Multi-layer clustering algorithm to reduce alert noise:
- Layer 1: Exact Match (70% coverage) - Fast O(n) grouping
- Layer 2: Temporal (20% coverage) - Time-window based
- Layer 3: Semantic (10% coverage) - ML-based similarity

Target: 60-80% noise reduction
"""
import logging
import hashlib
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.models import Alert, AlertCluster, utc_now

logger = logging.getLogger(__name__)


class AlertClusteringService:
    """Multi-layer alert clustering service"""

    def __init__(self, db: Session):
        self.db = db

    # ========== PUBLIC API ==========

    def cluster_alerts(
        self,
        alerts: List[Alert],
        strategy: str = 'auto'
    ) -> Dict[str, List[UUID]]:
        """
        Cluster alerts using selected strategy

        Args:
            alerts: List of Alert objects to cluster
            strategy: 'auto', 'exact', 'temporal', 'semantic'

        Returns:
            Dict mapping cluster_key to list of alert IDs
        """
        if not alerts:
            return {}

        logger.info(f"Clustering {len(alerts)} alerts using strategy: {strategy}")

        if strategy == 'exact':
            clusters = self._exact_match_clustering(alerts)
        elif strategy == 'temporal':
            cluster_groups = self._temporal_clustering(alerts)
            clusters = self._convert_temporal_to_dict(cluster_groups)
        elif strategy == 'semantic':
            cluster_groups = self._semantic_clustering(alerts)
            clusters = self._convert_semantic_to_dict(cluster_groups)
        else:  # auto
            # Layer 1: Exact match (catches 70%)
            exact_match_groups = self._exact_match_clustering(alerts)
            
            # Divide into clusters (size > 1) and unclustered (size == 1)
            clusters = {}
            unclustered = []
            
            for key, alert_list in exact_match_groups.items():
                if len(alert_list) > 1:
                    clusters[key] = alert_list
                else:
                    unclustered.extend(alert_list)

            # Layer 2: Temporal on remaining alerts
            if unclustered:
                temporal_groups = self._temporal_clustering(unclustered)
                temporal_clusters = self._convert_temporal_to_dict(temporal_groups)
                
                # Merge clusters
                for key, alert_list in temporal_clusters.items():
                    clusters[key] = alert_list
                    
                # Find alerts still unclustered
                clustered_ids = set()
                for alert_list in temporal_clusters.values():
                    clustered_ids.update(a.id for a in alert_list)
                
                unclustered = [a for a in unclustered if a.id not in clustered_ids]
            
            # Layer 3: Semantic on remaining alerts
            if unclustered:
                semantic_groups = self._semantic_clustering(unclustered)
                semantic_clusters = self._convert_semantic_to_dict(semantic_groups)
                
                # Merge clusters
                for key, alert_list in semantic_clusters.items():
                    clusters[key] = alert_list

        # Convert Alert objects to IDs
        result = {}
        for key, alert_list in clusters.items():
            result[key] = [a.id for a in alert_list]

        logger.info(f"Clustering complete: {len(alerts)} alerts → {len(result)} clusters")

        return result

    def apply_clustering(
        self,
        clusters: Dict[str, List[UUID]]
    ) -> List[AlertCluster]:
        """
        Save clustering results to database

        Args:
            clusters: Dict of cluster_key → alert_ids

        Returns:
            List of created/updated AlertCluster objects
        """
        created_clusters = []

        for cluster_key, alert_ids in clusters.items():
            # Skip single-alert clusters
            if len(alert_ids) < 2:
                continue

            # Get alerts
            alerts = self.db.query(Alert).filter(Alert.id.in_(alert_ids)).all()

            if not alerts:
                continue

            # Check if cluster exists
            existing = self.db.query(AlertCluster).filter(
                AlertCluster.cluster_key == cluster_key
            ).first()

            if existing:
                # Update existing cluster
                self._update_cluster(existing, alerts)
                created_clusters.append(existing)
            else:
                # Create new cluster
                cluster = self._create_cluster(cluster_key, alerts)
                created_clusters.append(cluster)

            # Link alerts to cluster
            for alert in alerts:
                if not alert.cluster_id:
                    alert.cluster_id = existing.id if existing else cluster.id
                    alert.clustered_at = utc_now()

        self.db.commit()

        logger.info(f"Applied clustering: {len(created_clusters)} clusters saved")

        return created_clusters

    def close_inactive_clusters(self, inactive_hours: int = 24) -> int:
        """
        Close clusters with no new alerts for specified hours

        Args:
            inactive_hours: Hours of inactivity before closing

        Returns:
            Number of clusters closed
        """
        cutoff_time = utc_now() - timedelta(hours=inactive_hours)

        inactive_clusters = self.db.query(AlertCluster).filter(
            AlertCluster.is_active == True,
            AlertCluster.last_seen < cutoff_time
        ).all()

        count = 0
        for cluster in inactive_clusters:
            cluster.is_active = False
            cluster.closed_at = utc_now()
            cluster.closed_reason = 'timeout'
            count += 1

        self.db.commit()

        logger.info(f"Closed {count} inactive clusters")

        return count

    # ========== LAYER 1: EXACT MATCH ==========

    def _exact_match_clustering(
        self,
        alerts: List[Alert]
    ) -> Dict[str, List[Alert]]:
        """
        Group alerts with identical name, instance, job
        Fast O(n) algorithm
        """
        clusters = defaultdict(list)

        for alert in alerts:
            key = self._generate_exact_key(alert)
            clusters[key].append(alert)

        logger.debug(f"Exact match: {len(alerts)} alerts → {len(clusters)} clusters")

        return dict(clusters)

    def _generate_exact_key(self, alert: Alert) -> str:
        """Generate unique key for exact match clustering"""
        # Use MD5 hash for consistent key length
        key_parts = [
            alert.alert_name or '',
            alert.instance or '',
            alert.job or ''
        ]
        key_string = '|'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    # ========== LAYER 2: TEMPORAL ==========

    def _temporal_clustering(
        self,
        alerts: List[Alert],
        window_minutes: int = 5
    ) -> List[List[Alert]]:
        """
        Group alerts with same name within time window
        Catches alert storms
        """
        # Group by alert name first
        by_name = defaultdict(list)
        for alert in alerts:
            by_name[alert.alert_name].append(alert)

        clusters = []

        for alert_name, alert_list in by_name.items():
            # Sort by timestamp
            sorted_alerts = sorted(alert_list, key=lambda a: a.timestamp)

            # Group into time windows
            current_cluster = []
            for alert in sorted_alerts:
                if not current_cluster:
                    current_cluster.append(alert)
                else:
                    # Check if within window
                    time_diff = alert.timestamp - current_cluster[-1].timestamp
                    if time_diff.total_seconds() / 60 <= window_minutes:
                        current_cluster.append(alert)
                    else:
                        # Start new cluster
                        if len(current_cluster) > 1:
                            clusters.append(current_cluster)
                        current_cluster = [alert]

            # Add last cluster
            if len(current_cluster) > 1:
                clusters.append(current_cluster)

        logger.debug(f"Temporal: {len(alerts)} alerts → {len(clusters)} clusters")

        return clusters

    def _convert_temporal_to_dict(
        self,
        cluster_groups: List[List[Alert]]
    ) -> Dict[str, List[Alert]]:
        """Convert temporal cluster groups to dict format"""
        result = {}
        for group in cluster_groups:
            if len(group) < 2:
                continue

            # Generate key from first alert + timestamp
            first_alert = group[0]
            key_parts = [
                first_alert.alert_name or '',
                first_alert.timestamp.strftime('%Y%m%d%H%M')
            ]
            key_string = '|'.join(key_parts)
            key = hashlib.md5(key_string.encode()).hexdigest()

            result[key] = group

        return result

    # ========== LAYER 3: SEMANTIC (OPTIONAL) ==========

    def _semantic_clustering(
        self,
        alerts: List[Alert],
        similarity_threshold: float = 0.7
    ) -> List[List[Alert]]:
        """
        Group alerts with similar descriptions using TF-IDF + cosine similarity
        Only runs on unclustered alerts (<10%)
        """
        if len(alerts) < 2:
            return []

        # Convert alerts to text
        alert_texts = [self._alert_to_text(a) for a in alerts]

        try:
            # TF-IDF vectorization
            vectorizer = TfidfVectorizer(
                max_features=100,
                stop_words='english',
                ngram_range=(1, 2)
            )
            tfidf_matrix = vectorizer.fit_transform(alert_texts)

            # Compute cosine similarity
            similarity_matrix = cosine_similarity(tfidf_matrix)

            # Find clusters using similarity threshold
            clustered = set()
            clusters = []

            for i in range(len(alerts)):
                if i in clustered:
                    continue

                # Find similar alerts
                similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]

                if len(similar_indices) > 1:
                    cluster = [alerts[j] for j in similar_indices if j not in clustered]
                    if len(cluster) > 1:
                        clusters.append(cluster)
                        clustered.update(similar_indices)

            logger.debug(f"Semantic: {len(alerts)} alerts → {len(clusters)} clusters")

            return clusters

        except Exception as e:
            logger.error(f"Semantic clustering failed: {e}")
            return []

    def _alert_to_text(self, alert: Alert) -> str:
        """Convert alert to text for semantic analysis"""
        parts = [
            alert.alert_name or '',
            alert.instance or '',
            alert.job or ''
        ]

        # Add annotations if available
        if alert.annotations_json:
            summary = alert.annotations_json.get('summary', '')
            description = alert.annotations_json.get('description', '')
            parts.extend([summary, description])

        return ' '.join(parts)

    def _convert_semantic_to_dict(
        self,
        cluster_groups: List[List[Alert]]
    ) -> Dict[str, List[Alert]]:
        """Convert semantic cluster groups to dict format"""
        result = {}
        for i, group in enumerate(cluster_groups):
            if len(group) < 2:
                continue

            # Generate key from first alert
            first_alert = group[0]
            key_parts = [
                'semantic',
                first_alert.alert_name or '',
                str(i)
            ]
            key_string = '|'.join(key_parts)
            key = hashlib.md5(key_string.encode()).hexdigest()

            result[key] = group

        return result

    # ========== HELPER METHODS ==========

    def _create_cluster(
        self,
        cluster_key: str,
        alerts: List[Alert]
    ) -> AlertCluster:
        """Create new cluster from alerts"""
        cluster = AlertCluster(
            cluster_key=cluster_key,
            alert_count=len(alerts),
            first_seen=min(a.timestamp for a in alerts),
            last_seen=max(a.timestamp for a in alerts),
            severity=self._calculate_severity(alerts),
            cluster_type='exact',  # Default, can be updated
            cluster_metadata=self._extract_metadata(alerts),
            is_active=True
        )

        self.db.add(cluster)
        self.db.flush()  # Get ID without committing

        logger.debug(f"Created cluster {cluster_key} with {len(alerts)} alerts")

        return cluster

    def _update_cluster(
        self,
        cluster: AlertCluster,
        alerts: List[Alert]
    ):
        """Update existing cluster with new alerts"""
        cluster.alert_count = len(alerts)
        cluster.first_seen = min(a.timestamp for a in alerts)
        cluster.last_seen = max(a.timestamp for a in alerts)
        cluster.severity = self._calculate_severity(alerts)
        cluster.cluster_metadata = self._extract_metadata(alerts)
        cluster.updated_at = utc_now()

        logger.debug(f"Updated cluster {cluster.cluster_key} with {len(alerts)} alerts")

    def _calculate_severity(self, alerts: List[Alert]) -> str:
        """Calculate highest severity from alerts"""
        severity_order = {'critical': 3, 'warning': 2, 'info': 1}
        severities = [a.severity for a in alerts if a.severity]

        if not severities:
            return 'info'

        return max(severities, key=lambda s: severity_order.get(s, 0))

    def _extract_metadata(self, alerts: List[Alert]) -> Dict:
        """Extract common metadata from alerts"""
        # Get common labels
        all_labels = [a.labels_json or {} for a in alerts]

        if not all_labels:
            return {}

        # Find common keys
        common_keys = set(all_labels[0].keys())
        for labels in all_labels[1:]:
            common_keys &= set(labels.keys())

        common_labels = {}
        for key in common_keys:
            # Check if all values are the same
            values = [labels.get(key) for labels in all_labels]
            if len(set(values)) == 1:
                common_labels[key] = values[0]

        # Extract affected services and instances
        services = set()
        instances = set()

        for alert in alerts:
            if alert.job:
                services.add(alert.job)
            if alert.instance:
                instances.add(alert.instance)

        return {
            'common_labels': common_labels,
            'affected_services': list(services),
            'affected_instances': list(instances)[:10],  # Limit to 10
            'unique_instances_count': len(instances)
        }
