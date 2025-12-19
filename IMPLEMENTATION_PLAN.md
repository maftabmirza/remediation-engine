# AIOps Platform - 6-Week Implementation Plan

**Version:** 1.0
**Date:** 2025-01-15
**Duration:** 6 weeks (42 days)
**Goal:** Implement Alert Clustering, MTTR Deep Dive, and Change Correlation

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Week 1-2: Alert Clustering](#week-1-2-alert-clustering)
4. [Week 3-4: MTTR Deep Dive](#week-3-4-mttr-deep-dive)
5. [Week 5-6: Change Correlation](#week-5-6-change-correlation)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Guide](#deployment-guide)
8. [Appendix](#appendix)

---

## Overview

### Project Goals

**Week 1-2: Alert Clustering**
- **Problem:** Alert noise - 500+ individual alerts overwhelming dashboard
- **Solution:** Multi-layer clustering to group related alerts
- **Target:** 60-80% noise reduction (500 alerts → 50-80 clusters)

**Week 3-4: MTTR Deep Dive**
- **Problem:** Simple average MTTR doesn't show problem areas
- **Solution:** Advanced analytics with percentiles, breakdowns, trends
- **Target:** Identify slow services, detect MTTR regressions

**Week 5-6: Change Correlation**
- **Problem:** Can't correlate incidents with deployments/changes
- **Solution:** Pluggable ITSM integration with impact scoring
- **Target:** Auto-detect which changes cause incidents

### Success Metrics

| Feature | Metric | Target |
|---------|--------|--------|
| Alert Clustering | Noise Reduction | 60-80% |
| Alert Clustering | Clustering Time | <5s for 1000 alerts |
| MTTR Analytics | Query Performance | <3s for 50k incidents |
| MTTR Analytics | Dashboard Load Time | <2s |
| Change Correlation | ITSM Sync Time | <30s for 1000 changes |
| Change Correlation | Correlation Accuracy | >80% |

---

## System Architecture

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AIOps Platform (Current)                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Prometheus/Alertmanager                                    │
│         │                                                    │
│         │ Webhook (Alert Fired)                             │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │  Rules Engine    │──► auto_analyze / manual / ignore    │
│  └──────────────────┘                                       │
│         │                                                    │
│         │ (if auto_analyze)                                 │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │  LLM Service     │──► Analysis + Recommendations        │
│  └──────────────────┘                                       │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │  PostgreSQL DB   │                                       │
│  │  - alerts        │                                       │
│  │  - users         │                                       │
│  │  - rules         │                                       │
│  └──────────────────┘                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Enhanced Architecture (After 6 Weeks)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AIOps Platform (Enhanced)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Prometheus/Alertmanager          ITSM Systems (ServiceNow/Jira)   │
│         │                                   │                        │
│         │ Webhook                          │ REST API               │
│         ▼                                   ▼                        │
│  ┌──────────────────┐              ┌──────────────────┐            │
│  │  Rules Engine    │              │ ITSM Connector   │            │
│  └──────────────────┘              │ (Generic API)    │            │
│         │                           └──────────────────┘            │
│         ▼                                   │                        │
│  ┌──────────────────┐                      │                        │
│  │ Clustering       │◄─────────────────────┘                        │
│  │ Worker (5min)    │                                               │
│  └──────────────────┘                                               │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │              PostgreSQL Database                         │       │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────┐ │       │
│  │  │ alerts       │  │ alert_clusters   │  │ change_    │ │       │
│  │  │ - cluster_id │  │ - cluster_key    │  │ events     │ │       │
│  │  └──────────────┘  │ - summary (AI)   │  └────────────┘ │       │
│  │                     └──────────────────┘                  │       │
│  │  ┌──────────────────┐  ┌─────────────────────────────┐  │       │
│  │  │ incident_metrics │  │ change_impact_analysis      │  │       │
│  │  │ - time_to_detect │  │ - correlation_score         │  │       │
│  │  │ - time_to_resolve│  │ - recommendation            │  │       │
│  │  └──────────────────┘  └─────────────────────────────┘  │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │                    New Dashboards                        │       │
│  │  - Clustered Alerts View                                 │       │
│  │  - Reliability Dashboard (MTTR Analytics)                │       │
│  │  - Change Impact Dashboard                               │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

# Week 1-2: Alert Clustering

## Overview

**Goal:** Reduce alert noise by 60-80% through intelligent clustering

**Strategy:** 3-layer clustering approach
1. **Exact Match** (70% of alerts) - Fast, deterministic
2. **Temporal** (20% of alerts) - Time-window based
3. **Semantic** (10% of alerts) - ML-based similarity

## Day 1-2: Database Schema

### Task 1.1: Create Migration

**File:** `alembic/versions/018_add_alert_clustering.py`

**SQL Schema:**

```sql
-- alert_clusters table
CREATE TABLE alert_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cluster_key VARCHAR(255) UNIQUE NOT NULL,
    alert_count INTEGER DEFAULT 1 NOT NULL,
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    severity VARCHAR(20) NOT NULL,
    cluster_type VARCHAR(50) DEFAULT 'exact' NOT NULL,
    summary TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE,
    closed_reason VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_cluster_key ON alert_clusters(cluster_key);
CREATE INDEX idx_cluster_first_seen ON alert_clusters(first_seen);
CREATE INDEX idx_cluster_last_seen ON alert_clusters(last_seen);
CREATE INDEX idx_cluster_severity ON alert_clusters(severity);
CREATE INDEX idx_cluster_active ON alert_clusters(is_active);

-- Modify alerts table
ALTER TABLE alerts ADD COLUMN cluster_id UUID REFERENCES alert_clusters(id) ON DELETE SET NULL;
ALTER TABLE alerts ADD COLUMN clustered_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_alert_cluster ON alerts(cluster_id);
```

**Migration Code:**

```python
"""Add alert clustering

Revision ID: 018
Revises: 017
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None

def upgrade():
    # Create alert_clusters table
    op.create_table('alert_clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cluster_key', sa.String(255), nullable=False, unique=True),
        sa.Column('alert_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('cluster_type', sa.String(50), nullable=False, server_default='exact'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_reason', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Create indexes
    op.create_index('idx_cluster_key', 'alert_clusters', ['cluster_key'], unique=True)
    op.create_index('idx_cluster_first_seen', 'alert_clusters', ['first_seen'])
    op.create_index('idx_cluster_last_seen', 'alert_clusters', ['last_seen'])
    op.create_index('idx_cluster_severity', 'alert_clusters', ['severity'])
    op.create_index('idx_cluster_active', 'alert_clusters', ['is_active'])

    # Add columns to alerts
    op.add_column('alerts', sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('alerts', sa.Column('clustered_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key
    op.create_foreign_key('fk_alert_cluster', 'alerts', 'alert_clusters', ['cluster_id'], ['id'], ondelete='SET NULL')

    # Create index
    op.create_index('idx_alert_cluster', 'alerts', ['cluster_id'])

def downgrade():
    op.drop_index('idx_alert_cluster', table_name='alerts')
    op.drop_constraint('fk_alert_cluster', 'alerts', type_='foreignkey')
    op.drop_column('alerts', 'clustered_at')
    op.drop_column('alerts', 'cluster_id')

    op.drop_index('idx_cluster_active', table_name='alert_clusters')
    op.drop_index('idx_cluster_severity', table_name='alert_clusters')
    op.drop_index('idx_cluster_last_seen', table_name='alert_clusters')
    op.drop_index('idx_cluster_first_seen', table_name='alert_clusters')
    op.drop_index('idx_cluster_key', table_name='alert_clusters')

    op.drop_table('alert_clusters')
```

**Testing:**

```bash
# Run migration
alembic upgrade head

# Verify tables created
psql -d aiops -c "\d alert_clusters"
psql -d aiops -c "\d alerts" | grep cluster

# Test rollback
alembic downgrade -1
alembic upgrade head
```

### Task 1.2: Create Models

**File:** `app/models.py`

Add to existing file:

```python
class AlertCluster(Base):
    """Alert cluster for grouping related alerts"""
    __tablename__ = "alert_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_key = Column(String(255), unique=True, nullable=False, index=True)
    alert_count = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen = Column(DateTime(timezone=True), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    cluster_type = Column(String(50), default='exact', nullable=False)
    summary = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_reason = Column(String(100), nullable=True)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    alerts = relationship("Alert", back_populates="cluster")

    @property
    def duration_hours(self) -> float:
        """Calculate cluster duration in hours"""
        if not self.first_seen or not self.last_seen:
            return 0.0
        delta = self.last_seen - self.first_seen
        return delta.total_seconds() / 3600

    @property
    def alerts_per_hour(self) -> float:
        """Calculate alert frequency"""
        if self.duration_hours == 0:
            return float(self.alert_count)
        return self.alert_count / self.duration_hours

    def update_stats(self, db: Session):
        """Recalculate cluster statistics"""
        alerts = db.query(Alert).filter(Alert.cluster_id == self.id).all()

        if not alerts:
            return

        self.alert_count = len(alerts)
        self.first_seen = min(a.timestamp for a in alerts)
        self.last_seen = max(a.timestamp for a in alerts)

        # Update severity to highest
        severity_order = {'critical': 3, 'warning': 2, 'info': 1}
        severities = [a.severity for a in alerts if a.severity]
        if severities:
            self.severity = max(severities, key=lambda s: severity_order.get(s, 0))

        self.updated_at = utc_now()

    def should_close(self, inactive_hours: int = 24) -> bool:
        """Check if cluster should be closed due to inactivity"""
        if not self.is_active:
            return False

        inactive_duration = utc_now() - self.last_seen
        return inactive_duration.total_seconds() / 3600 >= inactive_hours


# Update Alert model
class Alert(Base):
    # ... existing fields ...

    # Add clustering fields
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("alert_clusters.id"), nullable=True, index=True)
    clustered_at = Column(DateTime(timezone=True), nullable=True)

    # Add relationship
    cluster = relationship("AlertCluster", back_populates="alerts")
```

**File:** `app/schemas.py`

Add schemas:

```python
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class AlertClusterBase(BaseModel):
    cluster_key: str
    severity: str
    cluster_type: str = 'exact'

class AlertClusterCreate(AlertClusterBase):
    first_seen: datetime
    last_seen: datetime
    alert_count: int = 1

class AlertClusterResponse(AlertClusterBase):
    id: UUID
    alert_count: int
    first_seen: datetime
    last_seen: datetime
    summary: Optional[str] = None
    is_active: bool
    closed_at: Optional[datetime] = None
    closed_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Computed fields
    duration_hours: float
    alerts_per_hour: float

    class Config:
        from_attributes = True

class AlertClusterDetail(AlertClusterResponse):
    """Cluster with member alerts"""
    alerts: List['AlertResponse'] = []
    metadata: dict = {}

class AlertClusterStats(BaseModel):
    """Clustering statistics"""
    time_range: str
    total_alerts: int
    clustered_alerts: int
    unclustered_alerts: int
    total_clusters: int
    active_clusters: int
    noise_reduction_pct: float
    severity_breakdown: dict
```

**Acceptance Criteria:**
- [ ] Migration runs successfully
- [ ] Models created with all relationships
- [ ] Schemas validate correctly
- [ ] Computed properties work (duration_hours, alerts_per_hour)
- [ ] Migration can be rolled back cleanly

---

## Day 3-5: Clustering Service

### Task 2.1: Install Dependencies

**File:** `requirements.txt`

Add:

```txt
# ML & Clustering
scikit-learn==1.4.0
numpy==1.26.3
scipy==1.12.0
```

Install:

```bash
pip install scikit-learn==1.4.0 numpy==1.26.3 scipy==1.12.0
```

### Task 2.2: Create AlertClusteringService

**File:** `app/services/alert_clustering_service.py`

```python
"""
Alert Clustering Service

Multi-layer clustering strategy:
1. Exact Match - Group identical alerts (fast, O(n))
2. Temporal - Group alerts in time windows (medium)
3. Semantic - ML-based similarity (slow, optional)
"""
import logging
import hashlib
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Alert, AlertCluster
from app.utils.datetime import utc_now

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
            exact_clusters = self._exact_match_clustering(alerts)

            # Flatten to get clustered alerts
            clustered_ids = set()
            for alert_list in exact_clusters.values():
                clustered_ids.update(a.id for a in alert_list)

            # Layer 2: Temporal on remaining alerts
            unclustered = [a for a in alerts if a.id not in clustered_ids]

            if unclustered:
                temporal_groups = self._temporal_clustering(unclustered)
                temporal_clusters = self._convert_temporal_to_dict(temporal_groups)

                # Merge clusters
                clusters = exact_clusters
                for key, alert_list in temporal_clusters.items():
                    clusters[key] = alert_list
            else:
                clusters = exact_clusters

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

        # Filter to only multi-alert clusters
        return {k: v for k, v in clusters.items() if len(v) >= 2}

    def _generate_exact_key(self, alert: Alert) -> str:
        """Generate cluster key from alert attributes"""
        components = [
            alert.alert_name or '',
            alert.instance or '',
            alert.job or ''
        ]
        raw_key = '|'.join(components)

        # Hash for consistent key length
        return f"exact_{hashlib.md5(raw_key.encode()).hexdigest()[:16]}"

    # ========== LAYER 2: TEMPORAL ==========

    def _temporal_clustering(
        self,
        alerts: List[Alert],
        window_minutes: int = 5
    ) -> List[List[Alert]]:
        """
        Group same alert_name within time window
        Catches alert storms
        """
        # Sort by timestamp
        sorted_alerts = sorted(alerts, key=lambda a: a.timestamp)

        clusters = []
        current_cluster = []

        for alert in sorted_alerts:
            if not current_cluster:
                current_cluster.append(alert)
                continue

            last_alert = current_cluster[-1]
            time_diff = (alert.timestamp - last_alert.timestamp).total_seconds() / 60
            same_name = alert.alert_name == last_alert.alert_name

            if time_diff <= window_minutes and same_name:
                current_cluster.append(alert)
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [alert]

        # Don't forget last cluster
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        return clusters

    def _convert_temporal_to_dict(
        self,
        cluster_groups: List[List[Alert]]
    ) -> Dict[str, List[Alert]]:
        """Convert temporal cluster groups to dict format"""
        result = {}

        for idx, alerts in enumerate(cluster_groups):
            if not alerts:
                continue

            # Generate key from first alert + timestamp
            first = alerts[0]
            timestamp_key = first.timestamp.strftime('%Y%m%d%H%M')
            key = f"temporal_{first.alert_name}_{timestamp_key}_{idx}"
            result[key] = alerts

        return result

    # ========== LAYER 3: SEMANTIC (OPTIONAL) ==========

    def _semantic_clustering(
        self,
        alerts: List[Alert],
        similarity_threshold: float = 0.7
    ) -> Dict[int, List[Alert]]:
        """
        Use TF-IDF + cosine similarity
        Only for unclustered alerts (typically <10%)
        """
        if len(alerts) < 2:
            return {}

        # Vectorize alert text
        texts = [self._alert_to_text(a) for a in alerts]

        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        try:
            vectors = vectorizer.fit_transform(texts)
        except ValueError:
            # Not enough data to vectorize
            return {}

        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(vectors)

        # Cluster by similarity
        clusters = {}
        processed = set()

        for i, alert in enumerate(alerts):
            if i in processed:
                continue

            cluster = [alert]
            processed.add(i)

            # Find similar alerts
            for j in range(i + 1, len(alerts)):
                if j in processed:
                    continue

                if similarity_matrix[i][j] >= similarity_threshold:
                    cluster.append(alerts[j])
                    processed.add(j)

            # Only keep multi-alert clusters
            if len(cluster) >= 2:
                clusters[i] = cluster

        return clusters

    def _convert_semantic_to_dict(
        self,
        cluster_groups: Dict[int, List[Alert]]
    ) -> Dict[str, List[Alert]]:
        """Convert semantic clusters to dict format"""
        result = {}

        for idx, alerts in cluster_groups.items():
            if not alerts:
                continue

            # Generate key from cluster ID
            key = f"semantic_{idx}_{utc_now().strftime('%Y%m%d%H%M%S')}"
            result[key] = alerts

        return result

    def _alert_to_text(self, alert: Alert) -> str:
        """Convert alert to text for vectorization"""
        parts = [
            alert.alert_name or '',
            alert.description or '',
            str(alert.labels_json or {}),
            str(alert.annotations_json or {})
        ]
        return ' '.join(parts)

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
            cluster_type=self._detect_cluster_type(cluster_key),
            metadata=self._extract_metadata(alerts),
            is_active=True
        )

        self.db.add(cluster)
        self.db.flush()  # Get ID

        return cluster

    def _update_cluster(
        self,
        cluster: AlertCluster,
        new_alerts: List[Alert]
    ):
        """Update existing cluster with new alerts"""
        all_alerts = self.db.query(Alert).filter(
            Alert.cluster_id == cluster.id
        ).all()

        all_alerts.extend(new_alerts)

        cluster.alert_count = len(all_alerts)
        cluster.last_seen = max(a.timestamp for a in all_alerts)
        cluster.severity = self._calculate_severity(all_alerts)
        cluster.metadata = self._extract_metadata(all_alerts)
        cluster.updated_at = utc_now()

        # Reactivate if closed
        if not cluster.is_active:
            cluster.is_active = True
            cluster.closed_at = None
            cluster.closed_reason = None

    def _calculate_severity(self, alerts: List[Alert]) -> str:
        """Return highest severity in cluster"""
        severity_order = {'critical': 3, 'warning': 2, 'info': 1}
        severities = [a.severity for a in alerts if a.severity]

        if not severities:
            return 'info'

        return max(severities, key=lambda s: severity_order.get(s, 0))

    def _detect_cluster_type(self, cluster_key: str) -> str:
        """Detect cluster type from key"""
        if cluster_key.startswith('exact_'):
            return 'exact'
        elif cluster_key.startswith('temporal_'):
            return 'temporal'
        elif cluster_key.startswith('semantic_'):
            return 'semantic'
        else:
            return 'manual'

    def _extract_metadata(self, alerts: List[Alert]) -> dict:
        """Extract common metadata from alerts"""
        if not alerts:
            return {}

        # Find common labels
        common_labels = {}
        first_labels = alerts[0].labels_json or {}

        for key, value in first_labels.items():
            if all((a.labels_json or {}).get(key) == value for a in alerts):
                common_labels[key] = value

        # Extract services
        services = set()
        for alert in alerts:
            service = (alert.labels_json or {}).get('service') or \
                     (alert.labels_json or {}).get('job')
            if service:
                services.add(service)

        # Extract instances
        instances = set(a.instance for a in alerts if a.instance)

        return {
            'common_labels': common_labels,
            'affected_services': list(services),
            'affected_instances': list(instances),
            'unique_instances': len(instances)
        }

    async def generate_cluster_summary(
        self,
        cluster: AlertCluster,
        llm_service
    ) -> str:
        """
        Generate AI summary for cluster

        Args:
            cluster: AlertCluster object
            llm_service: LLM service instance

        Returns:
            Generated summary text
        """
        # Get sample alerts (up to 10)
        alerts = self.db.query(Alert).filter(
            Alert.cluster_id == cluster.id
        ).limit(10).all()

        if not alerts:
            return "No alerts in cluster"

        # Build prompt
        alert_samples = '\n'.join([
            f"- {a.alert_name} on {a.instance} at {a.timestamp}"
            for a in alerts
        ])

        prompt = f"""Analyze this alert cluster and provide a concise summary.

Cluster Statistics:
- Total Alerts: {cluster.alert_count}
- Time Span: {cluster.first_seen.strftime('%Y-%m-%d %H:%M')} to {cluster.last_seen.strftime('%Y-%m-%d %H:%M')}
- Duration: {cluster.duration_hours:.1f} hours
- Severity: {cluster.severity}
- Affected Services: {cluster.metadata.get('affected_services', [])}

Sample Alerts:
{alert_samples}

Provide a 3-4 sentence summary covering:
1. Root pattern (what's the common issue?)
2. Impact scope
3. Likely cause

Keep it concise and actionable."""

        try:
            summary, _ = await llm_service.generate_completion(
                self.db,
                prompt
            )
            return summary
        except Exception as e:
            logger.error(f"Failed to generate cluster summary: {e}")
            return f"Error generating summary: {str(e)}"
```

**Acceptance Criteria:**
- [ ] Exact match clustering works on 1000 alerts in <1s
- [ ] Temporal clustering correctly groups time-based alerts
- [ ] Semantic clustering achieves >70% accuracy
- [ ] All layers can be used independently or combined
- [ ] Metadata extraction works correctly

---

## Day 6-7: Background Worker

### Task 3.1: Create Clustering Worker

**File:** `app/services/clustering_worker.py`

```python
"""
Background job for automatic alert clustering
Runs every 5 minutes
"""
import logging
from datetime import timedelta
from typing import List

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Alert, AlertCluster
from app.services.alert_clustering_service import AlertClusteringService
from app.services.llm_service import get_default_provider
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)

# Configuration
CLUSTERING_INTERVAL_MINUTES = 5
CLUSTERING_WINDOW_HOURS = 1
CLUSTER_CLOSE_THRESHOLD_HOURS = 24
MIN_ALERTS_PER_CLUSTER = 2


async def cluster_recent_alerts():
    """
    Main clustering job

    1. Fetch unclustered alerts from last hour
    2. Run clustering
    3. Save results to database
    4. Close inactive clusters
    5. Generate AI summaries (async)
    """
    db = SessionLocal()

    try:
        # Step 1: Fetch unclustered alerts
        window_start = utc_now() - timedelta(hours=CLUSTERING_WINDOW_HOURS)

        unclustered_alerts = db.query(Alert).filter(
            Alert.cluster_id == None,
            Alert.timestamp >= window_start
        ).all()

        if len(unclustered_alerts) < MIN_ALERTS_PER_CLUSTER:
            logger.info(f"Clustering skipped: only {len(unclustered_alerts)} unclustered alerts")
            return

        logger.info(f"Starting clustering for {len(unclustered_alerts)} alerts...")

        # Step 2: Run clustering
        service = AlertClusteringService(db)
        clusters = service.cluster_alerts(unclustered_alerts, strategy='auto')

        if not clusters:
            logger.info("No clusters formed")
            return

        # Step 3: Save to database
        created_clusters = service.apply_clustering(clusters)

        # Step 4: Close inactive clusters
        closed_count = service.close_inactive_clusters(
            inactive_hours=CLUSTER_CLOSE_THRESHOLD_HOURS
        )

        # Step 5: Generate summaries (async, non-blocking)
        if created_clusters:
            await _generate_summaries_async(created_clusters)

        # Log statistics
        total_clustered = sum(len(alert_ids) for alert_ids in clusters.values())
        reduction_pct = (1 - len(clusters) / len(unclustered_alerts)) * 100 if unclustered_alerts else 0

        logger.info(
            f"Clustering complete: "
            f"{len(unclustered_alerts)} alerts → {len(clusters)} clusters "
            f"({reduction_pct:.1f}% reduction). "
            f"Closed {closed_count} inactive clusters."
        )

    except Exception as e:
        logger.error(f"Clustering job failed: {e}", exc_info=True)
    finally:
        db.close()


async def _generate_summaries_async(clusters: List[AlertCluster]):
    """
    Generate AI summaries for new clusters
    Runs asynchronously to avoid blocking main clustering job
    """
    db = SessionLocal()

    try:
        provider = get_default_provider(db)
        if not provider:
            logger.warning("No LLM provider configured, skipping summary generation")
            return

        service = AlertClusteringService(db)

        for cluster in clusters:
            try:
                # Only generate for clusters with 3+ alerts
                if cluster.alert_count < 3:
                    continue

                # Skip if summary already exists
                if cluster.summary:
                    continue

                logger.info(f"Generating summary for cluster {cluster.id}...")

                summary = await service.generate_cluster_summary(cluster, provider)
                cluster.summary = summary
                db.commit()

                logger.info(f"Summary generated for cluster {cluster.id}")

            except Exception as e:
                logger.warning(f"Failed to generate summary for cluster {cluster.id}: {e}")
                continue

    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
    finally:
        db.close()


async def cleanup_old_clusters():
    """
    Daily cleanup job
    Delete inactive clusters older than 30 days
    """
    db = SessionLocal()

    try:
        cutoff_date = utc_now() - timedelta(days=30)

        deleted = db.query(AlertCluster).filter(
            AlertCluster.is_active == False,
            AlertCluster.closed_at < cutoff_date
        ).delete()

        db.commit()

        logger.info(f"Cleanup: deleted {deleted} old inactive clusters")

    except Exception as e:
        logger.error(f"Cleanup job failed: {e}", exc_info=True)
    finally:
        db.close()


def start_clustering_jobs(scheduler):
    """
    Register clustering jobs with APScheduler

    Args:
        scheduler: AsyncIOScheduler instance
    """
    # Main clustering job - every 5 minutes
    scheduler.add_job(
        cluster_recent_alerts,
        'interval',
        minutes=CLUSTERING_INTERVAL_MINUTES,
        id='cluster_alerts',
        replace_existing=True
    )

    # Cleanup job - daily at 2 AM
    scheduler.add_job(
        cleanup_old_clusters,
        'cron',
        hour=2,
        minute=0,
        id='cleanup_clusters',
        replace_existing=True
    )

    logger.info("✅ Clustering background jobs registered")
```

### Task 3.2: Integrate with Main App

**File:** `app/main.py`

Add to lifespan function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # ... existing startup code ...

    # Start clustering jobs
    logger.info("Starting clustering background jobs...")
    from app.services.clustering_worker import start_clustering_jobs
    start_clustering_jobs(scheduler)

    yield

    # ... existing shutdown code ...
```

**Testing:**

```bash
# Start application
./deploy.sh

# Check logs for clustering job
docker-compose logs -f app | grep -i cluster

# Manually trigger (for testing)
# In Python shell:
# >>> from app.services.clustering_worker import cluster_recent_alerts
# >>> import asyncio
# >>> asyncio.run(cluster_recent_alerts())
```

**Acceptance Criteria:**
- [ ] Job runs automatically every 5 minutes
- [ ] Successfully clusters new alerts
- [ ] Closes inactive clusters
- [ ] Generates AI summaries
- [ ] Logs meaningful statistics
- [ ] Handles errors gracefully

---

## Day 8-9: API Endpoints

### Task 4.1: Create Clusters Router

**File:** `app/routers/clusters.py`

Create new file:

```python
"""
Alert Clusters API Router
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import User, Alert, AlertCluster
from app.schemas import (
    AlertClusterResponse,
    AlertClusterDetail,
    AlertClusterStats,
    AlertResponse
)
from app.services.alert_clustering_service import AlertClusteringService
from app.services.llm_service import get_default_provider
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=List[AlertClusterResponse])
async def list_clusters(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    time_range: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List alert clusters with filters

    Returns paginated list of clusters sorted by most recent
    """
    from app.utils.datetime import utc_now
    from datetime import timedelta

    # Calculate time range
    time_windows = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }
    start_time = utc_now() - time_windows[time_range]

    # Build query
    query = db.query(AlertCluster).filter(
        AlertCluster.created_at >= start_time
    )

    if is_active is not None:
        query = query.filter(AlertCluster.is_active == is_active)

    if severity:
        query = query.filter(AlertCluster.severity == severity)

    # Order by last_seen desc
    query = query.order_by(desc(AlertCluster.last_seen))

    # Paginate
    total = query.count()
    clusters = query.offset((page - 1) * page_size).limit(page_size).all()

    return clusters


@router.get("/{cluster_id}", response_model=AlertClusterDetail)
async def get_cluster(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get cluster details including member alerts"""
    cluster = db.query(AlertCluster).filter(
        AlertCluster.id == cluster_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    return cluster


@router.get("/{cluster_id}/alerts", response_model=List[AlertResponse])
async def get_cluster_alerts(
    cluster_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get paginated alerts in a cluster"""
    # Verify cluster exists
    cluster = db.query(AlertCluster).filter(
        AlertCluster.id == cluster_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Get paginated alerts
    query = db.query(Alert).filter(Alert.cluster_id == cluster_id)
    query = query.order_by(desc(Alert.timestamp))

    alerts = query.offset((page - 1) * page_size).limit(page_size).all()

    return alerts


@router.post("/{cluster_id}/close")
async def close_cluster(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually close/resolve a cluster"""
    cluster = db.query(AlertCluster).filter(
        AlertCluster.id == cluster_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    if not cluster.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cluster already closed"
        )

    from app.utils.datetime import utc_now
    cluster.is_active = False
    cluster.closed_at = utc_now()
    cluster.closed_reason = 'manual'

    db.commit()
    db.refresh(cluster)

    return {
        "status": "closed",
        "cluster_id": cluster.id,
        "message": "Cluster marked as resolved"
    }


@router.post("/{cluster_id}/merge/{target_cluster_id}")
async def merge_clusters(
    cluster_id: UUID,
    target_cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Merge two clusters

    Moves all alerts from source cluster to target cluster
    """
    source = db.query(AlertCluster).filter(
        AlertCluster.id == cluster_id
    ).first()

    target = db.query(AlertCluster).filter(
        AlertCluster.id == target_cluster_id
    ).first()

    if not source or not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both clusters not found"
        )

    # Move all alerts from source to target
    moved = db.query(Alert).filter(Alert.cluster_id == cluster_id).update({
        'cluster_id': target_cluster_id
    })

    # Update target cluster stats
    target.update_stats(db)

    # Close source cluster
    from app.utils.datetime import utc_now
    source.is_active = False
    source.closed_at = utc_now()
    source.closed_reason = 'merged'

    db.commit()

    return {
        "status": "merged",
        "source_cluster_id": str(cluster_id),
        "target_cluster_id": str(target_cluster_id),
        "alerts_moved": moved
    }


@router.post("/{cluster_id}/regenerate-summary")
async def regenerate_summary(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate AI summary for a cluster"""
    cluster = db.query(AlertCluster).filter(
        AlertCluster.id == cluster_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Get LLM provider
    provider = get_default_provider(db)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No LLM provider configured"
        )

    # Generate new summary
    service = AlertClusteringService(db)
    summary = await service.generate_cluster_summary(cluster, provider)

    cluster.summary = summary
    db.commit()
    db.refresh(cluster)

    return {
        "status": "regenerated",
        "cluster_id": str(cluster.id),
        "summary": summary
    }


@router.get("/stats/overview", response_model=AlertClusterStats)
async def get_clustering_stats(
    time_range: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get clustering statistics

    Returns metrics on noise reduction and cluster breakdown
    """
    from app.utils.datetime import utc_now
    from datetime import timedelta
    from sqlalchemy import func

    time_windows = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }
    start_time = utc_now() - time_windows[time_range]

    # Total alerts in range
    total_alerts = db.query(Alert).filter(
        Alert.timestamp >= start_time
    ).count()

    # Clustered alerts
    clustered_alerts = db.query(Alert).filter(
        Alert.timestamp >= start_time,
        Alert.cluster_id != None
    ).count()

    # Total clusters
    total_clusters = db.query(AlertCluster).filter(
        AlertCluster.created_at >= start_time
    ).count()

    # Active clusters
    active_clusters = db.query(AlertCluster).filter(
        AlertCluster.created_at >= start_time,
        AlertCluster.is_active == True
    ).count()

    # Calculate noise reduction
    if total_alerts > 0:
        # Effective alerts = unclustered + number of clusters (not individual alerts)
        unclustered = total_alerts - clustered_alerts
        effective_alerts = unclustered + total_clusters
        noise_reduction_pct = (1 - effective_alerts / total_alerts) * 100
    else:
        noise_reduction_pct = 0

    # Severity breakdown
    severity_breakdown = dict(
        db.query(
            AlertCluster.severity,
            func.count(AlertCluster.id)
        ).filter(
            AlertCluster.created_at >= start_time
        ).group_by(AlertCluster.severity).all()
    )

    return AlertClusterStats(
        time_range=time_range,
        total_alerts=total_alerts,
        clustered_alerts=clustered_alerts,
        unclustered_alerts=total_alerts - clustered_alerts,
        total_clusters=total_clusters,
        active_clusters=active_clusters,
        noise_reduction_pct=round(noise_reduction_pct, 1),
        severity_breakdown=severity_breakdown
    )
```

### Task 4.2: Register Router

**File:** `app/main.py`

Add import and include router:

```python
from app.routers import clusters

# In app setup
app.include_router(clusters.router)
```

**Testing:**

```bash
# Test API endpoints
curl http://localhost:8080/api/clusters?time_range=24h
curl http://localhost:8080/api/clusters/stats/overview

# Access API docs
open http://localhost:8080/docs
```

**Acceptance Criteria:**
- [ ] All endpoints respond correctly
- [ ] Pagination works properly
- [ ] Filters apply correctly
- [ ] Merge functionality works
- [ ] Statistics calculate accurately
- [ ] OpenAPI documentation generated

---

## Day 10: Dashboard UI Updates

### Task 5.1: Update Dashboard Stats

**File:** `templates/dashboard.html`

Add clustering stats card (after existing stats):

```html
<!-- Add after existing stat cards around line 96 -->
<div class="card p-5">
    <div class="flex items-center justify-between">
        <div>
            <p class="text-gray-400 text-sm">Active Clusters</p>
            <p class="text-3xl font-bold mt-1" id="statClusters">--</p>
            <p class="text-xs mt-1">
                <span id="noiseReduction" class="text-green-400 font-semibold">--</span>
                <span class="text-gray-500">noise reduction</span>
            </p>
        </div>
        <div class="w-12 h-12 rounded-lg bg-purple-500 bg-opacity-20 flex items-center justify-center">
            <i class="fas fa-layer-group text-purple-400 text-xl"></i>
        </div>
    </div>
</div>
```

Update JavaScript (in `<script>` section):

```javascript
async function loadDashboardStats() {
    try {
        // ... existing stats loading ...

        // Load clustering stats
        const clusterRes = await apiCall('/api/clusters/stats/overview?time_range=24h');
        if (clusterRes.ok) {
            const stats = await clusterRes.json();
            document.getElementById('statClusters').textContent = stats.active_clusters;
            document.getElementById('noiseReduction').textContent = stats.noise_reduction_pct.toFixed(1) + '%';
        }
    } catch (e) {
        console.error('Failed to load dashboard stats:', e);
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    setInterval(loadDashboardStats, 60000); // Refresh every minute
});
```

### Task 5.2: Update Alerts Page with Clustered View

**File:** `templates/alerts.html`

Add view toggle and clustered view container:

```html
<!-- Add after page header -->
<div class="flex justify-between items-center mb-6">
    <div>
        <h1 class="text-2xl font-bold">Alerts</h1>
        <p class="text-gray-400">Monitor and manage system alerts</p>
    </div>

    <!-- View Toggle -->
    <div class="flex items-center space-x-2">
        <button id="btnGroupedView" onclick="switchView('grouped')"
                class="px-4 py-2 rounded-lg bg-purple-600 text-white font-medium transition-colors">
            <i class="fas fa-layer-group mr-2"></i>Grouped View
        </button>
        <button id="btnIndividualView" onclick="switchView('individual')"
                class="px-4 py-2 rounded-lg bg-gray-700 text-gray-300 font-medium hover:bg-gray-600 transition-colors">
            <i class="fas fa-list mr-2"></i>Individual View
        </button>
    </div>
</div>

<!-- Clustered View Container -->
<div id="clusteredView" class="space-y-4">
    <div class="text-center py-8">
        <i class="fas fa-spinner fa-spin text-3xl text-purple-400"></i>
        <p class="text-gray-400 mt-2">Loading clusters...</p>
    </div>
</div>

<!-- Individual View Container (existing alerts table) -->
<div id="individualView" class="hidden">
    <!-- Your existing alerts table code stays here -->
</div>
```

Add JavaScript at end of file:

```javascript
<script>
let currentView = 'grouped';

function switchView(view) {
    currentView = view;

    const groupedView = document.getElementById('clusteredView');
    const individualView = document.getElementById('individualView');
    const btnGrouped = document.getElementById('btnGroupedView');
    const btnIndividual = document.getElementById('btnIndividualView');

    if (view === 'grouped') {
        groupedView.classList.remove('hidden');
        individualView.classList.add('hidden');
        btnGrouped.className = 'px-4 py-2 rounded-lg bg-purple-600 text-white font-medium transition-colors';
        btnIndividual.className = 'px-4 py-2 rounded-lg bg-gray-700 text-gray-300 font-medium hover:bg-gray-600 transition-colors';

        loadClusteredView();
    } else {
        groupedView.classList.add('hidden');
        individualView.classList.remove('hidden');
        btnGrouped.className = 'px-4 py-2 rounded-lg bg-gray-700 text-gray-300 font-medium hover:bg-gray-600 transition-colors';
        btnIndividual.className = 'px-4 py-2 rounded-lg bg-purple-600 text-white font-medium transition-colors';

        loadAlerts(); // Your existing function
    }
}

async function loadClusteredView() {
    const container = document.getElementById('clusteredView');
    container.innerHTML = '<div class="text-center py-8"><i class="fas fa-spinner fa-spin text-3xl text-purple-400"></i></div>';

    try {
        const res = await apiCall('/api/clusters?is_active=true&time_range=24h&page_size=50');
        if (!res.ok) throw new Error('Failed to load clusters');

        const clusters = await res.json();

        if (clusters.length === 0) {
            container.innerHTML = `
                <div class="card p-8 text-center">
                    <i class="fas fa-inbox text-4xl text-gray-600 mb-3"></i>
                    <p class="text-gray-400">No active clusters</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';

        for (const cluster of clusters) {
            const clusterCard = createClusterCard(cluster);
            container.appendChild(clusterCard);
        }
    } catch (e) {
        container.innerHTML = `
            <div class="card p-8 text-center">
                <i class="fas fa-exclamation-triangle text-4xl text-red-500 mb-3"></i>
                <p class="text-gray-400">Failed to load clusters</p>
                <button onclick="loadClusteredView()" class="btn-secondary mt-4">Retry</button>
            </div>
        `;
        console.error('Failed to load clusters:', e);
    }
}

function createClusterCard(cluster) {
    const card = document.createElement('div');
    card.className = 'card p-5 cursor-pointer hover:border-purple-500 transition-all';
    card.onclick = () => toggleClusterExpand(cluster.id);

    const severityColors = {
        'critical': 'text-red-400 bg-red-900',
        'warning': 'text-yellow-400 bg-yellow-900',
        'info': 'text-blue-400 bg-blue-900'
    };

    const severityIcons = {
        'critical': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };

    const severityColor = severityColors[cluster.severity] || 'text-gray-400 bg-gray-800';
    const severityIcon = severityIcons[cluster.severity] || 'fa-bell';

    const durationText = cluster.duration_hours < 1
        ? `${Math.round(cluster.duration_hours * 60)}m`
        : `${cluster.duration_hours.toFixed(1)}h`;

    card.innerHTML = `
        <div class="flex items-start justify-between">
            <div class="flex-grow">
                <div class="flex items-center space-x-3 mb-3">
                    <i class="fas ${severityIcon} ${severityColor.split(' ')[0]} text-2xl"></i>
                    <h3 class="font-bold text-lg">${escapeHtml(cluster.cluster_key.split('_')[1] || cluster.cluster_key)}</h3>
                    <span class="px-3 py-1 rounded-full text-xs font-semibold ${severityColor} bg-opacity-20">
                        ${cluster.severity.toUpperCase()}
                    </span>
                    <span class="px-2 py-1 rounded text-xs bg-gray-700 text-gray-400">
                        ${cluster.cluster_type}
                    </span>
                </div>

                <div class="flex items-center space-x-6 text-sm text-gray-400 mb-3">
                    <span><i class="fas fa-bell mr-1"></i>${cluster.alert_count} alerts</span>
                    <span><i class="fas fa-clock mr-1"></i>Started ${formatTimeAgo(cluster.first_seen)}</span>
                    <span><i class="fas fa-history mr-1"></i>Last ${formatTimeAgo(cluster.last_seen)}</span>
                    <span><i class="fas fa-stopwatch mr-1"></i>${durationText} duration</span>
                </div>

                ${cluster.summary ? `
                    <div class="text-sm text-gray-300 bg-gray-800 bg-opacity-50 p-3 rounded-lg mt-2 border-l-4 border-purple-500">
                        <i class="fas fa-robot text-purple-400 mr-2"></i>
                        <span class="font-semibold text-purple-300">AI Summary:</span>
                        ${escapeHtml(cluster.summary)}
                    </div>
                ` : ''}
            </div>

            <div class="flex items-center space-x-2 ml-6">
                <button onclick="analyzeCluster('${cluster.id}'); event.stopPropagation();"
                        class="btn-secondary px-3 py-2 text-sm whitespace-nowrap">
                    <i class="fas fa-brain mr-1"></i>Analyze
                </button>
                <button onclick="closeCluster('${cluster.id}'); event.stopPropagation();"
                        class="btn-primary px-3 py-2 text-sm whitespace-nowrap">
                    <i class="fas fa-check mr-1"></i>Resolve
                </button>
                <i class="fas fa-chevron-down text-gray-400 transition-transform" id="expand-icon-${cluster.id}"></i>
            </div>
        </div>

        <!-- Expandable alerts list -->
        <div id="cluster-alerts-${cluster.id}" class="hidden mt-4 border-t border-gray-700 pt-4">
            <p class="text-gray-400 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Loading alerts...</p>
        </div>
    `;

    return card;
}

async function toggleClusterExpand(clusterId) {
    const alertsDiv = document.getElementById(`cluster-alerts-${clusterId}`);
    const icon = document.getElementById(`expand-icon-${clusterId}`);

    if (alertsDiv.classList.contains('hidden')) {
        // Expand
        alertsDiv.classList.remove('hidden');
        icon.classList.add('rotate-180');

        // Load alerts
        try {
            const res = await apiCall(`/api/clusters/${clusterId}/alerts?page_size=20`);
            if (!res.ok) throw new Error('Failed to load alerts');

            const alerts = await res.json();

            if (alerts.length === 0) {
                alertsDiv.innerHTML = '<p class="text-gray-400 text-sm">No alerts in this cluster</p>';
                return;
            }

            alertsDiv.innerHTML = `
                <div class="space-y-2">
                    ${alerts.map(alert => `
                        <div class="flex items-center justify-between bg-gray-800 bg-opacity-50 p-3 rounded hover:bg-gray-750 transition-colors">
                            <div class="flex items-center space-x-4">
                                <i class="fas fa-arrow-right text-gray-600"></i>
                                <span class="font-medium text-gray-200">${escapeHtml(alert.alert_name)}</span>
                                <span class="text-sm text-gray-400">${escapeHtml(alert.instance || 'N/A')}</span>
                                <span class="text-xs text-gray-500">${formatDateTime(alert.timestamp)}</span>
                            </div>
                            <a href="/alerts/${alert.id}" class="btn-secondary px-3 py-1 text-sm">
                                View <i class="fas fa-external-link-alt ml-1"></i>
                            </a>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (e) {
            alertsDiv.innerHTML = '<p class="text-red-400 text-sm">Failed to load alerts</p>';
            console.error('Failed to load cluster alerts:', e);
        }
    } else {
        // Collapse
        alertsDiv.classList.add('hidden');
        icon.classList.remove('rotate-180');
    }
}

async function analyzeCluster(clusterId) {
    showToast('Generating AI analysis...', 'info');

    try {
        const res = await apiCall(`/api/clusters/${clusterId}/regenerate-summary`, {
            method: 'POST'
        });

        if (!res.ok) throw new Error('Analysis failed');

        showToast('Analysis complete!', 'success');
        await loadClusteredView(); // Refresh view
    } catch (e) {
        showToast('Failed to generate analysis', 'error');
        console.error('Failed to analyze cluster:', e);
    }
}

async function closeCluster(clusterId) {
    const confirmed = await showConfirmDialog(
        'Resolve Cluster',
        'Mark this cluster as resolved? All alerts will remain but the cluster will be closed.',
        'Resolve',
        'Cancel'
    );

    if (!confirmed) return;

    try {
        const res = await apiCall(`/api/clusters/${clusterId}/close`, {
            method: 'POST'
        });

        if (!res.ok) throw new Error('Failed to close cluster');

        showToast('Cluster resolved', 'success');
        await loadClusteredView(); // Refresh view
    } catch (e) {
        showToast('Failed to resolve cluster', 'error');
        console.error('Failed to close cluster:', e);
    }
}

// Helper functions
function formatTimeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
}

function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load on page load
document.addEventListener('DOMContentLoaded', () => {
    loadClusteredView();
    setInterval(loadClusteredView, 60000); // Refresh every minute
});
</script>
```

**Acceptance Criteria:**
- [ ] View toggle switches smoothly
- [ ] Clusters display correctly with all info
- [ ] Expand/collapse animation works
- [ ] AI summaries display properly
- [ ] Analyze button regenerates summaries
- [ ] Resolve button closes clusters
- [ ] Auto-refreshes every minute
- [ ] Responsive design

---

# Week 1-2 Acceptance Criteria

## Database
- [ ] Migration runs successfully forward and backward
- [ ] All indexes created
- [ ] Foreign keys work correctly
- [ ] Models match schema exactly

## Clustering Service
- [ ] Exact match: processes 1000 alerts in <1s
- [ ] Temporal: correctly groups time-based alerts
- [ ] Semantic: achieves >70% accuracy (optional)
- [ ] Auto strategy: combines layers effectively
- [ ] Metadata extraction works correctly

## Background Jobs
- [ ] Job runs every 5 minutes automatically
- [ ] Successfully clusters new alerts
- [ ] Closes inactive clusters after 24h
- [ ] Generates AI summaries asynchronously
- [ ] Logs meaningful statistics
- [ ] Handles errors gracefully

## API Endpoints
- [ ] All endpoints respond correctly
- [ ] Pagination works
- [ ] Filters apply correctly
- [ ] Merge functionality works
- [ ] Statistics accurate
- [ ] OpenAPI docs generated

## UI
- [ ] Dashboard shows clustering stats
- [ ] Alerts page has view toggle
- [ ] Grouped view displays clusters
- [ ] Expand/collapse works smoothly
- [ ] Actions (analyze, resolve) work
- [ ] Responsive design
- [ ] Auto-refresh works

## Performance
- [ ] Clustering 1000 alerts: <5s
- [ ] API response time: <500ms
- [ ] Dashboard load time: <2s
- [ ] Background job memory: <500MB

## Testing
- [ ] Unit tests: 80% coverage
- [ ] Integration tests pass
- [ ] E2E test: alert → cluster → resolve
- [ ] Load test: 10,000 alerts

## Success Metrics
- [ ] **Noise reduction: 60-80%** (500 alerts → 50-80 clusters)
- [ ] **Clustering accuracy: >90%** (manual validation)
- [ ] **User satisfaction: Positive feedback on dashboard UX**

---

**Continue to Week 3-4: MTTR Deep Dive?**

---

# Week 3-4: MTTR Deep Dive

## Overview

**Goal:** Advanced incident metrics with percentiles, breakdowns, and trend detection

**Current State:**
- Basic MTTR/MTTA calculation (simple averages)
- Displayed on dashboard but no deep insights

**Enhanced State:**
- Percentile analysis (p50, p95, p99)
- Breakdowns by service, severity, resolution type
- Trend detection and regression alerts
- Dedicated Reliability Dashboard

## Day 1-2: Database Schema

### Task 1.1: Create IncidentMetrics Migration

**File:** `alembic/versions/019_add_incident_metrics.py`

**SQL Schema:**

```sql
-- incident_metrics table
CREATE TABLE incident_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID UNIQUE NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    
    -- Lifecycle timestamps
    incident_started TIMESTAMP WITH TIME ZONE NOT NULL,
    incident_detected TIMESTAMP WITH TIME ZONE NOT NULL,
    incident_acknowledged TIMESTAMP WITH TIME ZONE,
    incident_engaged TIMESTAMP WITH TIME ZONE,
    incident_resolved TIMESTAMP WITH TIME ZONE,
    
    -- Calculated durations (in seconds)
    time_to_detect INTEGER,
    time_to_acknowledge INTEGER,
    time_to_engage INTEGER,
    time_to_resolve INTEGER,
    
    -- Context for breakdowns
    service_name VARCHAR(255),
    severity VARCHAR(20),
    resolution_type VARCHAR(50), -- automated, manual, escalated
    assigned_to UUID REFERENCES users(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_metrics_resolved ON incident_metrics(incident_resolved);
CREATE INDEX idx_metrics_service ON incident_metrics(service_name);
CREATE INDEX idx_metrics_severity ON incident_metrics(severity);
CREATE INDEX idx_metrics_resolution ON incident_metrics(resolution_type);
CREATE INDEX idx_metrics_alert ON incident_metrics(alert_id);
```

**Migration Code:**

```python
"""Add incident metrics

Revision ID: 019
Revises: 018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '019'
down_revision = '018'

def upgrade():
    op.create_table('incident_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        
        sa.Column('incident_started', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incident_detected', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incident_acknowledged', sa.DateTime(timezone=True)),
        sa.Column('incident_engaged', sa.DateTime(timezone=True)),
        sa.Column('incident_resolved', sa.DateTime(timezone=True)),
        
        sa.Column('time_to_detect', sa.Integer()),
        sa.Column('time_to_acknowledge', sa.Integer()),
        sa.Column('time_to_engage', sa.Integer()),
        sa.Column('time_to_resolve', sa.Integer()),
        
        sa.Column('service_name', sa.String(255)),
        sa.Column('severity', sa.String(20)),
        sa.Column('resolution_type', sa.String(50)),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True)),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Foreign keys
    op.create_foreign_key('fk_metrics_alert', 'incident_metrics', 'alerts', ['alert_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_metrics_user', 'incident_metrics', 'users', ['assigned_to'], ['id'], ondelete='SET NULL')

    # Indexes
    op.create_index('idx_metrics_resolved', 'incident_metrics', ['incident_resolved'])
    op.create_index('idx_metrics_service', 'incident_metrics', ['service_name'])
    op.create_index('idx_metrics_severity', 'incident_metrics', ['severity'])
    op.create_index('idx_metrics_resolution', 'incident_metrics', ['resolution_type'])
    op.create_index('idx_metrics_alert', 'incident_metrics', ['alert_id'])

def downgrade():
    op.drop_index('idx_metrics_alert', table_name='incident_metrics')
    op.drop_index('idx_metrics_resolution', table_name='incident_metrics')
    op.drop_index('idx_metrics_severity', table_name='incident_metrics')
    op.drop_index('idx_metrics_service', table_name='incident_metrics')
    op.drop_index('idx_metrics_resolved', table_name='incident_metrics')
    
    op.drop_constraint('fk_metrics_user', 'incident_metrics', type_='foreignkey')
    op.drop_constraint('fk_metrics_alert', 'incident_metrics', type_='foreignkey')
    
    op.drop_table('incident_metrics')
```

### Task 1.2: Create Models

**File:** `app/models.py`

Add model:

```python
class IncidentMetrics(Base):
    """Detailed incident timeline metrics"""
    __tablename__ = "incident_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Lifecycle timestamps
    incident_started = Column(DateTime(timezone=True), nullable=False)
    incident_detected = Column(DateTime(timezone=True), nullable=False)
    incident_acknowledged = Column(DateTime(timezone=True))
    incident_engaged = Column(DateTime(timezone=True))
    incident_resolved = Column(DateTime(timezone=True))

    # Calculated durations (seconds)
    time_to_detect = Column(Integer)
    time_to_acknowledge = Column(Integer)
    time_to_engage = Column(Integer)
    time_to_resolve = Column(Integer)

    # Context
    service_name = Column(String(255), index=True)
    severity = Column(String(20), index=True)
    resolution_type = Column(String(50), index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    alert = relationship("Alert", back_populates="metrics")
    assignee = relationship("User")

    def calculate_durations(self):
        """Calculate all time_to_* fields from timestamps"""
        if self.incident_detected and self.incident_started:
            self.time_to_detect = int((self.incident_detected - self.incident_started).total_seconds())

        if self.incident_acknowledged and self.incident_detected:
            self.time_to_acknowledge = int((self.incident_acknowledged - self.incident_detected).total_seconds())

        if self.incident_engaged and self.incident_acknowledged:
            self.time_to_engage = int((self.incident_engaged - self.incident_acknowledged).total_seconds())

        if self.incident_resolved and self.incident_engaged:
            self.time_to_resolve = int((self.incident_resolved - self.incident_engaged).total_seconds())

# Update Alert model
class Alert(Base):
    # ... existing code ...

    # Add relationship
    metrics = relationship("IncidentMetrics", back_populates="alert", uselist=False)
```

**File:** `app/schemas.py`

Add schemas:

```python
class IncidentMetricsBase(BaseModel):
    incident_started: datetime
    incident_detected: datetime
    service_name: Optional[str] = None
    severity: Optional[str] = None

class IncidentMetricsCreate(IncidentMetricsBase):
    alert_id: UUID

class IncidentMetricsUpdate(BaseModel):
    incident_acknowledged: Optional[datetime] = None
    incident_engaged: Optional[datetime] = None
    incident_resolved: Optional[datetime] = None
    resolution_type: Optional[str] = None
    assigned_to: Optional[UUID] = None

class IncidentMetricsResponse(IncidentMetricsBase):
    id: UUID
    alert_id: UUID
    incident_acknowledged: Optional[datetime]
    incident_engaged: Optional[datetime]
    incident_resolved: Optional[datetime]
    time_to_detect: Optional[int]
    time_to_acknowledge: Optional[int]
    time_to_engage: Optional[int]
    time_to_resolve: Optional[int]
    resolution_type: Optional[str]

    class Config:
        from_attributes = True

# Analytics schemas
class MTTRAnalytics(BaseModel):
    """MTTR analytics response"""
    avg: float
    p50: float
    p95: float
    p99: float
    sample_size: int
    unit: str = "seconds"

class MTTRBreakdown(BaseModel):
    """MTTR breakdown by dimension"""
    dimension: str  # service, severity, resolution_type
    breakdown: Dict[str, MTTRAnalytics]

class TrendPoint(BaseModel):
    """Single point in trend chart"""
    timestamp: datetime
    value: float

class RegressionAlert(BaseModel):
    """MTTR regression detection"""
    status: str  # regression, healthy
    metric: str  # mttr, mtta
    current_value: float
    previous_value: float
    change_pct: float
    severity: str  # high, medium, low
    message: str
```

## Day 3: Metrics Collection Integration

### Task 2.1: Auto-Create Metrics on Alert Received

**File:** `app/routers/webhook.py`

Update webhook handler:

```python
# In webhook alert handler (after creating alert)

from app.models import IncidentMetrics

# Create incident metrics
metric = IncidentMetrics(
    alert_id=alert.id,
    incident_started=alert.timestamp,  # Assume alert time = incident start
    incident_detected=alert.timestamp,
    service_name=alert.labels_json.get('service') or alert.job,
    severity=alert.severity
)
metric.calculate_durations()

db.add(metric)
db.commit()
```

### Task 2.2: Update Metrics on Alert Actions

**File:** `app/routers/alerts.py`

Add endpoint to acknowledge alert:

```python
@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Acknowledge an alert (start MTTA timer)"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    # Update metrics
    metric = db.query(IncidentMetrics).filter(
        IncidentMetrics.alert_id == alert_id
    ).first()

    if metric and not metric.incident_acknowledged:
        metric.incident_acknowledged = utc_now()
        metric.assigned_to = current_user.id
        metric.calculate_durations()
        db.commit()

    return {"status": "acknowledged", "alert_id": str(alert_id)}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    resolution_type: str = "manual",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark alert as resolved (stop MTTR timer)"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    # Update metrics
    metric = db.query(IncidentMetrics).filter(
        IncidentMetrics.alert_id == alert_id
    ).first()

    if metric and not metric.incident_resolved:
        # Auto-set engaged time if not set
        if not metric.incident_engaged:
            metric.incident_engaged = metric.incident_acknowledged or utc_now()

        metric.incident_resolved = utc_now()
        metric.resolution_type = resolution_type
        metric.calculate_durations()
        db.commit()

    return {"status": "resolved", "alert_id": str(alert_id)}
```

### Task 2.3: Auto-Update on Runbook Execution

**File:** `app/services/runbook_executor.py`

Update executor (in execute method):

```python
# When runbook execution starts
from app.models import IncidentMetrics

if alert_id:
    metric = db.query(IncidentMetrics).filter(
        IncidentMetrics.alert_id == alert_id
    ).first()

    if metric and not metric.incident_engaged:
        metric.incident_engaged = utc_now()
        metric.resolution_type = 'automated'
        metric.calculate_durations()

# When runbook execution completes successfully
if execution.status == "success" and alert_id:
    metric = db.query(IncidentMetrics).filter(
        IncidentMetrics.alert_id == alert_id
    ).first()

    if metric and not metric.incident_resolved:
        metric.incident_resolved = utc_now()
        metric.calculate_durations()
```

## Day 4-6: Analytics Service

### Task 3.1: Create MetricsAnalyticsService

**File:** `app/services/metrics_analytics_service.py`

```python
"""
MTTR/MTTA Analytics Service

Provides advanced metrics analysis:
- Percentile calculations
- Breakdowns by dimensions
- Trend analysis
- Regression detection
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import IncidentMetrics
from app.schemas import MTTRAnalytics, MTTRBreakdown, TrendPoint, RegressionAlert

logger = logging.getLogger(__name__)


class MetricsAnalyticsService:
    """Advanced MTTR/MTTA analytics"""

    def __init__(self, db: Session):
        self.db = db

    # ========== MTTR ANALYTICS ==========

    def get_mttr_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        service: Optional[str] = None,
        severity: Optional[str] = None
    ) -> MTTRAnalytics:
        """
        Get MTTR metrics with percentiles

        Args:
            start_date: Start of time range
            end_date: End of time range
            service: Filter by service (optional)
            severity: Filter by severity (optional)

        Returns:
            MTTRAnalytics with avg, p50, p95, p99
        """
        query = self.db.query(IncidentMetrics).filter(
            IncidentMetrics.incident_resolved.between(start_date, end_date),
            IncidentMetrics.time_to_resolve.isnot(None)
        )

        if service:
            query = query.filter(IncidentMetrics.service_name == service)

        if severity:
            query = query.filter(IncidentMetrics.severity == severity)

        metrics = query.all()

        if not metrics:
            return MTTRAnalytics(
                avg=0.0,
                p50=0.0,
                p95=0.0,
                p99=0.0,
                sample_size=0
            )

        values = [m.time_to_resolve for m in metrics]

        return MTTRAnalytics(
            avg=statistics.mean(values),
            p50=self._percentile(values, 50),
            p95=self._percentile(values, 95),
            p99=self._percentile(values, 99),
            sample_size=len(values)
        )

    def get_mtta_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        service: Optional[str] = None,
        severity: Optional[str] = None
    ) -> MTTRAnalytics:
        """Get MTTA (Mean Time To Acknowledge) metrics"""
        query = self.db.query(IncidentMetrics).filter(
            IncidentMetrics.incident_acknowledged.between(start_date, end_date),
            IncidentMetrics.time_to_acknowledge.isnot(None)
        )

        if service:
            query = query.filter(IncidentMetrics.service_name == service)

        if severity:
            query = query.filter(IncidentMetrics.severity == severity)

        metrics = query.all()

        if not metrics:
            return MTTRAnalytics(avg=0.0, p50=0.0, p95=0.0, p99=0.0, sample_size=0)

        values = [m.time_to_acknowledge for m in metrics]

        return MTTRAnalytics(
            avg=statistics.mean(values),
            p50=self._percentile(values, 50),
            p95=self._percentile(values, 95),
            p99=self._percentile(values, 99),
            sample_size=len(values)
        )

    # ========== BREAKDOWNS ==========

    def get_mttr_by_service(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> MTTRBreakdown:
        """Get MTTR breakdown by service"""
        services = self.db.query(IncidentMetrics.service_name).filter(
            IncidentMetrics.incident_resolved.between(start_date, end_date),
            IncidentMetrics.service_name.isnot(None)
        ).distinct().all()

        breakdown = {}

        for (service_name,) in services:
            analytics = self.get_mttr_analytics(
                start_date,
                end_date,
                service=service_name
            )
            breakdown[service_name] = analytics

        return MTTRBreakdown(
            dimension="service",
            breakdown=breakdown
        )

    def get_mttr_by_severity(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> MTTRBreakdown:
        """Get MTTR breakdown by severity"""
        severities = ['critical', 'warning', 'info']

        breakdown = {}

        for severity in severities:
            analytics = self.get_mttr_analytics(
                start_date,
                end_date,
                severity=severity
            )
            if analytics.sample_size > 0:
                breakdown[severity] = analytics

        return MTTRBreakdown(
            dimension="severity",
            breakdown=breakdown
        )

    def get_mttr_by_resolution_type(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> MTTRBreakdown:
        """Get MTTR breakdown by resolution type (automated vs manual)"""
        resolution_types = self.db.query(IncidentMetrics.resolution_type).filter(
            IncidentMetrics.incident_resolved.between(start_date, end_date),
            IncidentMetrics.resolution_type.isnot(None)
        ).distinct().all()

        breakdown = {}

        for (res_type,) in resolution_types:
            query = self.db.query(IncidentMetrics).filter(
                IncidentMetrics.incident_resolved.between(start_date, end_date),
                IncidentMetrics.resolution_type == res_type,
                IncidentMetrics.time_to_resolve.isnot(None)
            )

            metrics = query.all()

            if metrics:
                values = [m.time_to_resolve for m in metrics]
                breakdown[res_type] = MTTRAnalytics(
                    avg=statistics.mean(values),
                    p50=self._percentile(values, 50),
                    p95=self._percentile(values, 95),
                    p99=self._percentile(values, 99),
                    sample_size=len(values)
                )

        return MTTRBreakdown(
            dimension="resolution_type",
            breakdown=breakdown
        )

    # ========== TRENDS ==========

    def get_mttr_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        bucket_size: str = 'daily'  # hourly, daily, weekly
    ) -> List[TrendPoint]:
        """
        Get MTTR trend over time

        Args:
            start_date: Start date
            end_date: End date
            bucket_size: Time bucket size (hourly, daily, weekly)

        Returns:
            List of TrendPoint (timestamp, average MTTR)
        """
        from datetime import timedelta

        bucket_deltas = {
            'hourly': timedelta(hours=1),
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1)
        }

        delta = bucket_deltas.get(bucket_size, timedelta(days=1))

        trend = []
        current = start_date

        while current < end_date:
            bucket_end = min(current + delta, end_date)

            # Get MTTR for this bucket
            metrics = self.db.query(IncidentMetrics).filter(
                IncidentMetrics.incident_resolved.between(current, bucket_end),
                IncidentMetrics.time_to_resolve.isnot(None)
            ).all()

            if metrics:
                values = [m.time_to_resolve for m in metrics]
                avg_mttr = statistics.mean(values)
            else:
                avg_mttr = 0.0

            trend.append(TrendPoint(
                timestamp=current,
                value=avg_mttr
            ))

            current = bucket_end

        return trend

    # ========== REGRESSION DETECTION ==========

    def detect_mttr_regression(
        self,
        current_period_days: int = 7,
        comparison_period_days: int = 7,
        threshold_pct: float = 20.0
    ) -> RegressionAlert:
        """
        Detect if MTTR has regressed

        Compares current period vs previous period
        Alerts if MTTR increased by threshold_pct or more

        Args:
            current_period_days: Days in current period
            comparison_period_days: Days in comparison period
            threshold_pct: Alert if change >= this percentage

        Returns:
            RegressionAlert
        """
        from app.utils.datetime import utc_now

        now = utc_now()

        # Current period
        current_start = now - timedelta(days=current_period_days)
        current_metrics = self.get_mttr_analytics(current_start, now)

        # Previous period
        prev_start = current_start - timedelta(days=comparison_period_days)
        prev_metrics = self.get_mttr_analytics(prev_start, current_start)

        if prev_metrics.sample_size == 0 or current_metrics.sample_size == 0:
            return RegressionAlert(
                status="insufficient_data",
                metric="mttr",
                current_value=current_metrics.avg,
                previous_value=prev_metrics.avg,
                change_pct=0.0,
                severity="info",
                message="Not enough data to detect regression"
            )

        # Calculate change percentage
        change_pct = ((current_metrics.avg - prev_metrics.avg) / prev_metrics.avg) * 100

        if change_pct >= threshold_pct:
            status = "regression"
            severity = "high" if change_pct >= 50 else "medium"
            message = f"MTTR increased by {change_pct:.1f}% (from {self._format_seconds(prev_metrics.avg)} to {self._format_seconds(current_metrics.avg)})"
        elif change_pct <= -threshold_pct:
            status = "improvement"
            severity = "info"
            message = f"MTTR improved by {abs(change_pct):.1f}%"
        else:
            status = "healthy"
            severity = "info"
            message = f"MTTR stable (change: {change_pct:+.1f}%)"

        return RegressionAlert(
            status=status,
            metric="mttr",
            current_value=current_metrics.avg,
            previous_value=prev_metrics.avg,
            change_pct=change_pct,
            severity=severity,
            message=message
        )

    # ========== HELPER METHODS ==========

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)

        return sorted_values[index]

    def _format_seconds(self, seconds: float) -> str:
        """Format seconds to human-readable string"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
```

## Day 7: API Endpoints

### Task 4.1: Create Analytics Router

**File:** `app/routers/analytics.py`

```python
"""
MTTR/MTTA Analytics API Router
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import MTTRAnalytics, MTTRBreakdown, TrendPoint, RegressionAlert
from app.services.metrics_analytics_service import MetricsAnalyticsService
from app.routers.auth import get_current_user
from app.utils.datetime import utc_now

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/mttr", response_model=MTTRAnalytics)
async def get_mttr(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    service: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get MTTR metrics with percentiles"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }

    end_date = utc_now()
    start_date = end_date - time_deltas[time_range]

    service_obj = MetricsAnalyticsService(db)
    analytics = service_obj.get_mttr_analytics(
        start_date,
        end_date,
        service=service,
        severity=severity
    )

    return analytics


@router.get("/mtta", response_model=MTTRAnalytics)
async def get_mtta(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    service: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get MTTA (Mean Time To Acknowledge) metrics"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }

    end_date = utc_now()
    start_date = end_date - time_deltas[time_range]

    service_obj = MetricsAnalyticsService(db)
    analytics = service_obj.get_mtta_analytics(
        start_date,
        end_date,
        service=service,
        severity=severity
    )

    return analytics


@router.get("/mttr/breakdown", response_model=MTTRBreakdown)
async def get_mttr_breakdown(
    dimension: str = Query(..., regex="^(service|severity|resolution_type)$"),
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get MTTR breakdown by dimension"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }

    end_date = utc_now()
    start_date = end_date - time_deltas[time_range]

    service = MetricsAnalyticsService(db)

    if dimension == "service":
        return service.get_mttr_by_service(start_date, end_date)
    elif dimension == "severity":
        return service.get_mttr_by_severity(start_date, end_date)
    else:  # resolution_type
        return service.get_mttr_by_resolution_type(start_date, end_date)


@router.get("/mttr/trend", response_model=list[TrendPoint])
async def get_mttr_trend(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    bucket_size: str = Query("daily", regex="^(hourly|daily|weekly)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get MTTR trend over time"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }

    end_date = utc_now()
    start_date = end_date - time_deltas[time_range]

    service = MetricsAnalyticsService(db)
    trend = service.get_mttr_trend(start_date, end_date, bucket_size)

    return trend


@router.get("/regression", response_model=RegressionAlert)
async def detect_regression(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Detect MTTR regression (last 7 days vs previous 7 days)"""
    service = MetricsAnalyticsService(db)
    regression = service.detect_mttr_regression(
        current_period_days=7,
        comparison_period_days=7,
        threshold_pct=20.0
    )

    return regression


@router.get("/summary")
async def get_analytics_summary(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analytics summary
    Returns all metrics in one response (for dashboard)
    """
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }

    end_date = utc_now()
    start_date = end_date - time_deltas[time_range]

    service = MetricsAnalyticsService(db)

    # Get all metrics
    mttr = service.get_mttr_analytics(start_date, end_date)
    mtta = service.get_mtta_analytics(start_date, end_date)
    by_service = service.get_mttr_by_service(start_date, end_date)
    by_severity = service.get_mttr_by_severity(start_date, end_date)
    regression = service.detect_mttr_regression()

    return {
        "time_range": time_range,
        "mttr": mttr,
        "mtta": mtta,
        "breakdown_by_service": by_service.breakdown,
        "breakdown_by_severity": by_severity.breakdown,
        "regression_status": regression
    }
```

Register in `app/main.py`:

```python
from app.routers import analytics

app.include_router(analytics.router)
```

## Day 8-10: Reliability Dashboard

### Task 5.1: Create Reliability Page

**File:** `templates/reliability.html`

```html
{% extends "layout.html" %}
{% set active_page = 'reliability' %}

{% block title %}Reliability Dashboard - AIOps Platform{% endblock %}

{% block head %}
{{ super() }}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
        <div>
            <h1 class="text-2xl font-bold">Reliability Dashboard</h1>
            <p class="text-gray-400">MTTR/MTTA metrics and performance trends</p>
        </div>
        
        <div class="flex items-center space-x-2">
            <label class="text-sm text-gray-400">Time Range:</label>
            <select id="timeRange" class="input-field bg-gray-900 border-gray-700 rounded px-3 py-2" onchange="loadAllData()">
                <option value="24h">Last 24h</option>
                <option value="7d" selected>Last 7d</option>
                <option value="30d">Last 30d</option>
            </select>
        </div>
    </div>

    <!-- Regression Alert (if any) -->
    <div id="regressionAlert" class="hidden card border-l-4 border-red-500 p-4 bg-red-900 bg-opacity-20">
        <div class="flex items-start space-x-3">
            <i class="fas fa-exclamation-triangle text-red-400 text-xl mt-1"></i>
            <div class="flex-grow">
                <h3 class="font-bold text-red-300 mb-1" id="regressionTitle">MTTR Regression Detected</h3>
                <p class="text-sm text-red-200" id="regressionMessage"></p>
            </div>
        </div>
    </div>

    <!-- Key Metrics -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- Avg MTTR -->
        <div class="card p-5">
            <p class="text-gray-400 text-sm">Avg MTTR</p>
            <p class="text-3xl font-bold mt-1" id="avgMTTR">--</p>
            <p class="text-xs text-gray-500 mt-1">Mean time to resolve</p>
        </div>

        <!-- P95 MTTR -->
        <div class="card p-5">
            <p class="text-gray-400 text-sm">P95 MTTR</p>
            <p class="text-3xl font-bold mt-1" id="p95MTTR">--</p>
            <p class="text-xs text-gray-500 mt-1">95th percentile</p>
        </div>

        <!-- Avg MTTA -->
        <div class="card p-5">
            <p class="text-gray-400 text-sm">Avg MTTA</p>
            <p class="text-3xl font-bold mt-1" id="avgMTTA">--</p>
            <p class="text-xs text-gray-500 mt-1">Mean time to acknowledge</p>
        </div>

        <!-- Total Incidents -->
        <div class="card p-5">
            <p class="text-gray-400 text-sm">Total Incidents</p>
            <p class="text-3xl font-bold mt-1" id="totalIncidents">--</p>
            <p class="text-xs text-gray-500 mt-1">Resolved incidents</p>
        </div>
    </div>

    <!-- MTTR Trend Chart -->
    <div class="card p-6">
        <h3 class="font-bold text-lg mb-4">MTTR Trend</h3>
        <canvas id="mttrTrendChart" height="80"></canvas>
    </div>

    <!-- Breakdowns -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- MTTR by Service -->
        <div class="card p-6">
            <h3 class="font-bold text-lg mb-4">MTTR by Service</h3>
            <canvas id="serviceChart" height="200"></canvas>
        </div>

        <!-- MTTR by Severity -->
        <div class="card p-6">
            <h3 class="font-bold text-lg mb-4">MTTR by Severity</h3>
            <canvas id="severityChart" height="200"></canvas>
        </div>
    </div>

    <!-- Percentile Distribution Table -->
    <div class="card p-6">
        <h3 class="font-bold text-lg mb-4">Percentile Distribution</h3>
        <table class="w-full">
            <thead>
                <tr class="border-b border-gray-700">
                    <th class="text-left py-2 text-gray-400">Metric</th>
                    <th class="text-right py-2 text-gray-400">Average</th>
                    <th class="text-right py-2 text-gray-400">P50 (Median)</th>
                    <th class="text-right py-2 text-gray-400">P95</th>
                    <th class="text-right py-2 text-gray-400">P99</th>
                    <th class="text-right py-2 text-gray-400">Sample Size</th>
                </tr>
            </thead>
            <tbody id="percentileTable">
                <tr><td colspan="6" class="text-center py-4 text-gray-400">Loading...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<script>
let charts = {};

async function loadAllData() {
    const timeRange = document.getElementById('timeRange').value;
    
    try {
        // Load summary (all data in one call)
        const res = await apiCall(`/api/analytics/summary?time_range=${timeRange}`);
        if (!res.ok) throw new Error('Failed to load analytics');
        
        const data = await res.json();
        
        // Update key metrics
        updateKeyMetrics(data);
        
        // Update regression alert
        updateRegressionAlert(data.regression_status);
        
        // Update charts
        await updateMTTRTrend(timeRange);
        updateServiceChart(data.breakdown_by_service);
        updateSeverityChart(data.breakdown_by_severity);
        
        // Update percentile table
        updatePercentileTable(data);
        
    } catch (e) {
        console.error('Failed to load analytics:', e);
        showToast('Failed to load analytics data', 'error');
    }
}

function updateKeyMetrics(data) {
    document.getElementById('avgMTTR').textContent = formatDuration(data.mttr.avg);
    document.getElementById('p95MTTR').textContent = formatDuration(data.mttr.p95);
    document.getElementById('avgMTTA').textContent = formatDuration(data.mtta.avg);
    document.getElementById('totalIncidents').textContent = data.mttr.sample_size;
}

function updateRegressionAlert(regression) {
    const alert = document.getElementById('regressionAlert');
    
    if (regression.status === 'regression') {
        alert.classList.remove('hidden');
        document.getElementById('regressionMessage').textContent = regression.message;
    } else {
        alert.classList.add('hidden');
    }
}

async function updateMTTRTrend(timeRange) {
    const res = await apiCall(`/api/analytics/mttr/trend?time_range=${timeRange}&bucket_size=daily`);
    if (!res.ok) return;
    
    const trend = await res.json();
    
    const ctx = document.getElementById('mttrTrendChart');
    
    if (charts.trend) {
        charts.trend.destroy();
    }
    
    charts.trend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: trend.map(p => new Date(p.timestamp).toLocaleDateString()),
            datasets: [{
                label: 'MTTR (seconds)',
                data: trend.map(p => p.value),
                borderColor: 'rgb(147, 51, 234)',
                backgroundColor: 'rgba(147, 51, 234, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatDuration(value);
                        }
                    }
                }
            }
        }
    });
}

function updateServiceChart(breakdown) {
    const ctx = document.getElementById('serviceChart');
    
    if (charts.service) {
        charts.service.destroy();
    }
    
    const services = Object.keys(breakdown);
    const avgValues = services.map(s => breakdown[s].avg);
    
    charts.service = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: services,
            datasets: [{
                label: 'Avg MTTR',
                data: avgValues,
                backgroundColor: 'rgba(147, 51, 234, 0.7)',
                borderColor: 'rgb(147, 51, 234)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatDuration(value);
                        }
                    }
                }
            }
        }
    });
}

function updateSeverityChart(breakdown) {
    const ctx = document.getElementById('severityChart');
    
    if (charts.severity) {
        charts.severity.destroy();
    }
    
    const severities = Object.keys(breakdown);
    const avgValues = severities.map(s => breakdown[s].avg);
    
    const colors = {
        'critical': 'rgba(239, 68, 68, 0.7)',
        'warning': 'rgba(251, 191, 36, 0.7)',
        'info': 'rgba(59, 130, 246, 0.7)'
    };
    
    charts.severity = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: severities.map(s => s.toUpperCase()),
            datasets: [{
                data: avgValues,
                backgroundColor: severities.map(s => colors[s] || 'rgba(107, 114, 128, 0.7)'),
                borderWidth: 2,
                borderColor: '#1f2937'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function updatePercentileTable(data) {
    const tbody = document.getElementById('percentileTable');
    
    tbody.innerHTML = `
        <tr class="border-b border-gray-800">
            <td class="py-3 font-medium">MTTR</td>
            <td class="py-3 text-right">${formatDuration(data.mttr.avg)}</td>
            <td class="py-3 text-right">${formatDuration(data.mttr.p50)}</td>
            <td class="py-3 text-right">${formatDuration(data.mttr.p95)}</td>
            <td class="py-3 text-right">${formatDuration(data.mttr.p99)}</td>
            <td class="py-3 text-right text-gray-400">${data.mttr.sample_size}</td>
        </tr>
        <tr>
            <td class="py-3 font-medium">MTTA</td>
            <td class="py-3 text-right">${formatDuration(data.mtta.avg)}</td>
            <td class="py-3 text-right">${formatDuration(data.mtta.p50)}</td>
            <td class="py-3 text-right">${formatDuration(data.mtta.p95)}</td>
            <td class="py-3 text-right">${formatDuration(data.mtta.p99)}</td>
            <td class="py-3 text-right text-gray-400">${data.mtta.sample_size}</td>
        </tr>
    `;
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`;
    } else if (seconds < 3600) {
        return `${(seconds / 60).toFixed(1)}m`;
    } else {
        return `${(seconds / 3600).toFixed(1)}h`;
    }
}

// Load on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    setInterval(loadAllData, 300000); // Refresh every 5 minutes
});
</script>
{% endblock %}
```

### Task 5.2: Add to Navigation

**File:** `templates/layout.html`

Add menu item:

```html
<!-- In navigation menu -->
<a href="/reliability" class="nav-item {% if active_page == 'reliability' %}active{% endif %}">
    <i class="fas fa-chart-line mr-2"></i>Reliability
</a>
```

**File:** `app/main.py`

Add route:

```python
@app.get("/reliability", response_class=HTMLResponse)
async def reliability_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """Reliability dashboard page"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("reliability.html", {
        "request": request,
        "user": current_user
    })
```

# Week 3-4 Acceptance Criteria

## Database
- [ ] Migration runs successfully
- [ ] Metrics auto-created on alert received
- [ ] Durations calculated correctly
- [ ] All indexes present

## Metrics Collection
- [ ] Auto-create metrics on webhook
- [ ] Update on acknowledge
- [ ] Update on runbook execution
- [ ] Update on resolution

## Analytics Service
- [ ] Percentile calculations accurate
- [ ] Breakdowns work for all dimensions
- [ ] Trend data generated correctly
- [ ] Regression detection works
- [ ] Handles zero/null data gracefully

## API Endpoints
- [ ] All endpoints respond correctly
- [ ] Caching works (5-minute cache)
- [ ] Summary endpoint efficient
- [ ] Error handling proper

## Reliability Dashboard
- [ ] Key metrics display correctly
- [ ] Charts render properly
- [ ] Regression alert shows when needed
- [ ] Auto-refresh works
- [ ] Responsive design
- [ ] Performance: loads in <2s

## Testing
- [ ] Unit tests: 80% coverage
- [ ] Integration tests pass
- [ ] Performance test: 50k metrics in <3s
- [ ] E2E test: alert → metrics → analytics

## Success Metrics
- [ ] **Identify slow services** (MTTR by service shows problem areas)
- [ ] **Detect regressions** (20%+ MTTR increase alerts)
- [ ] **Percentile insights** (p95/p99 reveal outliers)

---

*Document continues with Week 5-6: Change Correlation...*


---

# Week 5-6: Change Correlation (Generic ITSM Integration)

## Overview

**Goal:** Detect which changes (deployments, configs) cause incidents through pluggable ITSM integration

**Architecture Decision:** Generic API approach (NOT per-ITSM connectors)
- **Flexible:** Works with ANY JSON API (ServiceNow, Jira, GitHub, custom tools)
- **Configurable:** Field mapping via JSONPath
- **Maintainable:** One connector vs. 10+ specific connectors

**Data Flow:**
```
ITSM System (any) → REST API → Generic Connector → Field Mapping → ChangeEvent → Correlation Analysis
```

## Day 1: Database Schema

### Task 1.1: Create ITSM Integration Schema

**File:** `alembic/versions/020_add_itsm_integration.py`

**SQL Schema:**

```sql
-- itsm_integrations table (stores ITSM connection configs)
CREATE TABLE itsm_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,  -- "Production ServiceNow"
    connector_type VARCHAR(50) DEFAULT 'generic_api' NOT NULL,
    
    -- Encrypted configuration JSON
    config_encrypted TEXT NOT NULL,
    
    -- Status
    is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    last_sync TIMESTAMP WITH TIME ZONE,
    last_sync_status VARCHAR(50),  -- success, failed, partial
    last_error TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_itsm_enabled ON itsm_integrations(is_enabled);
CREATE INDEX idx_itsm_last_sync ON itsm_integrations(last_sync);

-- change_events table (stores changes from ITSM)
CREATE TABLE change_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    change_id VARCHAR(255) UNIQUE NOT NULL,  -- CHG-001234 from ITSM
    change_type VARCHAR(50) NOT NULL,  -- deployment, config, scaling
    service_name VARCHAR(255),
    description TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    source VARCHAR(100),  -- integration_id or 'webhook'
    metadata JSONB DEFAULT '{}',  -- raw data from ITSM
    
    -- Correlation results
    correlation_score FLOAT,
    impact_level VARCHAR(20),  -- high, medium, low, none
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_change_id ON change_events(change_id);
CREATE INDEX idx_change_timestamp ON change_events(timestamp);
CREATE INDEX idx_change_service ON change_events(service_name);
CREATE INDEX idx_change_source ON change_events(source);
CREATE INDEX idx_change_correlation ON change_events(correlation_score);

-- change_impact_analysis table
CREATE TABLE change_impact_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    change_event_id UUID NOT NULL REFERENCES change_events(id) ON DELETE CASCADE,
    
    incidents_after INTEGER DEFAULT 0,
    critical_incidents INTEGER DEFAULT 0,
    correlation_score FLOAT NOT NULL,
    impact_level VARCHAR(20) NOT NULL,
    recommendation TEXT,
    
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_impact_change ON change_impact_analysis(change_event_id);
CREATE INDEX idx_impact_score ON change_impact_analysis(correlation_score);
```

**Migration Code:**

```python
"""Add ITSM integration and change correlation

Revision ID: 020
Revises: 019
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '020'
down_revision = '019'

def upgrade():
    # ITSM integrations table
    op.create_table('itsm_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False, server_default='generic_api'),
        sa.Column('config_encrypted', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_sync', sa.DateTime(timezone=True)),
        sa.Column('last_sync_status', sa.String(50)),
        sa.Column('last_error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_index('idx_itsm_enabled', 'itsm_integrations', ['is_enabled'])
    op.create_index('idx_itsm_last_sync', 'itsm_integrations', ['last_sync'])

    # Change events table
    op.create_table('change_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_id', sa.String(255), nullable=False, unique=True),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('service_name', sa.String(255)),
        sa.Column('description', sa.Text()),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(100)),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('correlation_score', sa.Float()),
        sa.Column('impact_level', sa.String(20)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_index('idx_change_id', 'change_events', ['change_id'], unique=True)
    op.create_index('idx_change_timestamp', 'change_events', ['timestamp'])
    op.create_index('idx_change_service', 'change_events', ['service_name'])
    op.create_index('idx_change_source', 'change_events', ['source'])
    op.create_index('idx_change_correlation', 'change_events', ['correlation_score'])

    # Change impact analysis table
    op.create_table('change_impact_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('incidents_after', sa.Integer(), server_default='0'),
        sa.Column('critical_incidents', sa.Integer(), server_default='0'),
        sa.Column('correlation_score', sa.Float(), nullable=False),
        sa.Column('impact_level', sa.String(20), nullable=False),
        sa.Column('recommendation', sa.Text()),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_foreign_key('fk_impact_change', 'change_impact_analysis', 'change_events',
                         ['change_event_id'], ['id'], ondelete='CASCADE')

    op.create_index('idx_impact_change', 'change_impact_analysis', ['change_event_id'])
    op.create_index('idx_impact_score', 'change_impact_analysis', ['correlation_score'])

def downgrade():
    op.drop_index('idx_impact_score', table_name='change_impact_analysis')
    op.drop_index('idx_impact_change', table_name='change_impact_analysis')
    op.drop_constraint('fk_impact_change', 'change_impact_analysis', type_='foreignkey')
    op.drop_table('change_impact_analysis')

    op.drop_index('idx_change_correlation', table_name='change_events')
    op.drop_index('idx_change_source', table_name='change_events')
    op.drop_index('idx_change_service', table_name='change_events')
    op.drop_index('idx_change_timestamp', table_name='change_events')
    op.drop_index('idx_change_id', table_name='change_events')
    op.drop_table('change_events')

    op.drop_index('idx_itsm_last_sync', table_name='itsm_integrations')
    op.drop_index('idx_itsm_enabled', table_name='itsm_integrations')
    op.drop_table('itsm_integrations')
```

### Task 1.2: Create Models

**File:** `app/models_itsm.py` (new file)

```python
"""
ITSM Integration Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.datetime import utc_now


class ITSMIntegration(Base):
    """ITSM system integration configuration"""
    __tablename__ = "itsm_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), default='generic_api', nullable=False)
    config_encrypted = Column(Text, nullable=False)  # Encrypted JSON config
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_sync = Column(DateTime(timezone=True), index=True)
    last_sync_status = Column(String(50))  # success, failed, partial
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ChangeEvent(Base):
    """Change/deployment event from ITSM system"""
    __tablename__ = "change_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_id = Column(String(255), unique=True, nullable=False, index=True)
    change_type = Column(String(50), nullable=False)
    service_name = Column(String(255), index=True)
    description = Column(Text)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(100), index=True)  # integration ID or 'webhook'
    metadata = Column(JSON, default={})
    correlation_score = Column(Float, index=True)
    impact_level = Column(String(20))  # high, medium, low, none
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    impact_analysis = relationship("ChangeImpactAnalysis", back_populates="change_event", uselist=False)


class ChangeImpactAnalysis(Base):
    """Analysis of change impact on incidents"""
    __tablename__ = "change_impact_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_event_id = Column(UUID(as_uuid=True), ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False)
    incidents_after = Column(Integer, default=0)
    critical_incidents = Column(Integer, default=0)
    correlation_score = Column(Float, nullable=False, index=True)
    impact_level = Column(String(20), nullable=False)
    recommendation = Column(Text)
    analyzed_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    change_event = relationship("ChangeEvent", back_populates="impact_analysis")
```

**File:** `app/schemas_itsm.py` (new file)

```python
"""
ITSM Integration Schemas
"""
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# ITSM Integration schemas
class ITSMConfigBase(BaseModel):
    """Base ITSM configuration"""
    name: str
    connector_type: str = 'generic_api'
    is_enabled: bool = True


class ITSMConfigCreate(ITSMConfigBase):
    """Create ITSM integration"""
    config: Dict[str, Any]  # Unencrypted config (will be encrypted)


class ITSMConfigResponse(ITSMConfigBase):
    """ITSM integration response"""
    id: UUID
    last_sync: Optional[datetime]
    last_sync_status: Optional[str]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Change Event schemas
class ChangeEventBase(BaseModel):
    """Base change event"""
    change_id: str
    change_type: str
    service_name: Optional[str]
    description: Optional[str]
    timestamp: datetime


class ChangeEventCreate(ChangeEventBase):
    """Create change event"""
    source: str = 'webhook'
    metadata: Dict[str, Any] = {}


class ChangeEventResponse(ChangeEventBase):
    """Change event response"""
    id: UUID
    source: str
    metadata: Dict[str, Any]
    correlation_score: Optional[float]
    impact_level: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Impact Analysis schemas
class ChangeImpactResponse(BaseModel):
    """Change impact analysis result"""
    change_id: str
    change_description: str
    timestamp: datetime
    correlation_score: float
    impact: str  # high, medium, low, none
    incidents_after: int
    critical_incidents: int
    recommendation: Optional[str]


# Configuration Templates
class ITSMConfigTemplate(BaseModel):
    """Pre-configured ITSM template"""
    name: str  # ServiceNow, Jira, GitHub
    description: str
    config_template: Dict[str, Any]
    field_mapping_example: Dict[str, str]
```

## Day 2-4: Generic API Connector

### Task 2.1: Install Dependencies

**File:** `requirements.txt`

Add:

```txt
# ITSM Integration
jsonpath-ng==1.6.1  # JSONPath parsing
requests==2.31.0    # HTTP client (already installed)
python-dateutil==2.8.2  # Date parsing
```

### Task 2.2: Create Generic Connector

**File:** `app/services/itsm_connector.py` (new file)

```python
"""
Generic ITSM API Connector

Supports ANY JSON API through configurable field mapping
"""
import logging
import json
import math
from typing import List, Dict, Optional, Any, Iterator
from datetime import datetime
from abc import ABC, abstractmethod

import requests
from jsonpath_ng import parse
from dateutil import parser as date_parser

from app.models_itsm import ChangeEvent
from app.utils.crypto import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)


# ========== AUTH HANDLERS ==========

class BaseAuthHandler(ABC):
    """Base class for authentication handlers"""

    @abstractmethod
    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Apply authentication to headers"""
        pass


class BearerTokenAuth(BaseAuthHandler):
    """Bearer token authentication"""

    def __init__(self, token: str):
        self.token = token

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers['Authorization'] = f'Bearer {self.token}'
        return headers


class BasicAuth(BaseAuthHandler):
    """HTTP Basic authentication"""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        import base64
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers['Authorization'] = f'Basic {encoded}'
        return headers


class APIKeyAuth(BaseAuthHandler):
    """API key in header"""

    def __init__(self, key: str, header_name: str = 'X-API-Key'):
        self.key = key
        self.header_name = header_name

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers[self.header_name] = self.key
        return headers


class AuthHandlerFactory:
    """Factory for creating auth handlers"""

    @staticmethod
    def create(auth_config: Dict[str, Any]) -> BaseAuthHandler:
        """
        Create auth handler from config

        Config formats:
        - Bearer: {"type": "bearer_token", "token": "xxx"}
        - Basic: {"type": "basic", "username": "user", "password": "pass"}
        - API Key: {"type": "api_key", "key": "xxx", "header_name": "X-API-Key"}
        """
        auth_type = auth_config.get('type', 'bearer_token')

        if auth_type == 'bearer_token':
            return BearerTokenAuth(auth_config['token'])
        elif auth_type == 'basic':
            return BasicAuth(auth_config['username'], auth_config['password'])
        elif auth_type == 'api_key':
            return APIKeyAuth(
                auth_config['key'],
                auth_config.get('header_name', 'X-API-Key')
            )
        else:
            raise ValueError(f"Unknown auth type: {auth_type}")


# ========== PAGINATION HANDLERS ==========

class BasePaginationHandler(ABC):
    """Base class for pagination handlers"""

    @abstractmethod
    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        """Get parameters for next page"""
        pass


class OffsetPagination(BasePaginationHandler):
    """Offset-based pagination (offset + limit)"""

    def __init__(self, config: Dict[str, Any]):
        self.offset_param = config.get('offset_param', 'offset')
        self.limit_param = config.get('limit_param', 'limit')
        self.page_size = config.get('page_size', 100)
        self.max_pages = config.get('max_pages', 10)

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        if page_num >= self.max_pages:
            return None

        current_offset = current_params.get(self.offset_param, 0)
        next_offset = current_offset + self.page_size

        return {
            **current_params,
            self.offset_param: next_offset,
            self.limit_param: self.page_size
        }


class PagePagination(BasePaginationHandler):
    """Page-based pagination (page + per_page)"""

    def __init__(self, config: Dict[str, Any]):
        self.page_param = config.get('page_param', 'page')
        self.per_page_param = config.get('per_page_param', 'per_page')
        self.page_size = config.get('page_size', 100)
        self.max_pages = config.get('max_pages', 10)

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        if page_num >= self.max_pages:
            return None

        next_page = page_num + 1

        return {
            **current_params,
            self.page_param: next_page,
            self.per_page_param: self.page_size
        }


class NoPagination(BasePaginationHandler):
    """No pagination - single request"""

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        return None  # Only one page


class PaginationHandlerFactory:
    """Factory for creating pagination handlers"""

    @staticmethod
    def create(pagination_config: Optional[Dict[str, Any]]) -> BasePaginationHandler:
        """
        Create pagination handler from config

        Config formats:
        - Offset: {"type": "offset", "offset_param": "offset", "limit_param": "limit", "page_size": 100}
        - Page: {"type": "page", "page_param": "page", "per_page_param": "per_page", "page_size": 100}
        - None: {"type": "none"} or None
        """
        if not pagination_config or pagination_config.get('type') == 'none':
            return NoPagination()

        pag_type = pagination_config.get('type', 'offset')

        if pag_type == 'offset':
            return OffsetPagination(pagination_config)
        elif pag_type == 'page':
            return PagePagination(pagination_config)
        else:
            raise ValueError(f"Unknown pagination type: {pag_type}")


# ========== FIELD MAPPER ==========

class FieldMapper:
    """Map ITSM fields to ChangeEvent fields using JSONPath"""

    def __init__(self, field_mapping: Dict[str, str], transformations: Optional[Dict[str, Dict]] = None):
        """
        Initialize field mapper

        Args:
            field_mapping: JSONPath expressions for each field
                Example: {"change_id": "$.result[*].number", "timestamp": "$.result[*].sys_created_on"}
            transformations: Optional transformations for fields
                Example: {"timestamp": {"type": "datetime", "format": "iso8601"}}
        """
        self.field_mapping = field_mapping
        self.transformations = transformations or {}

    def extract_fields(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract fields from JSON response using JSONPath

        Args:
            json_data: API response JSON

        Returns:
            List of dicts with mapped fields (one per change)
        """
        # Parse all JSONPath expressions
        parsed_paths = {}
        for field_name, json_path in self.field_mapping.items():
            try:
                parsed_paths[field_name] = parse(json_path)
            except Exception as e:
                logger.error(f"Invalid JSONPath for {field_name}: {json_path} - {e}")
                continue

        # Extract values for each field
        field_values = {}
        for field_name, path_expr in parsed_paths.items():
            try:
                matches = path_expr.find(json_data)
                field_values[field_name] = [m.value for m in matches]
            except Exception as e:
                logger.error(f"Error extracting {field_name}: {e}")
                field_values[field_name] = []

        # Determine number of records
        if not field_values:
            return []

        num_records = max(len(values) for values in field_values.values())

        # Build records
        records = []
        for i in range(num_records):
            record = {}
            for field_name, values in field_values.items():
                if i < len(values):
                    raw_value = values[i]
                    # Apply transformations
                    transformed_value = self._transform_value(field_name, raw_value)
                    record[field_name] = transformed_value

            # Only add complete records
            required_fields = ['change_id', 'timestamp']
            if all(field in record for field in required_fields):
                records.append(record)

        return records

    def _transform_value(self, field_name: str, value: Any) -> Any:
        """Apply transformations to field value"""
        if field_name not in self.transformations:
            return value

        transform = self.transformations[field_name]
        transform_type = transform.get('type')

        if transform_type == 'datetime':
            return self._parse_datetime(value, transform.get('format', 'iso8601'))
        elif transform_type == 'array_join':
            separator = transform.get('separator', ', ')
            return separator.join(str(v) for v in value) if isinstance(value, list) else str(value)
        else:
            return value

    def _parse_datetime(self, value: Any, format_type: str) -> datetime:
        """Parse datetime from various formats"""
        if isinstance(value, datetime):
            return value

        if format_type == 'iso8601':
            return date_parser.isoparse(str(value))
        elif format_type == 'unix_epoch':
            return datetime.fromtimestamp(int(value))
        else:
            # Try generic parser
            return date_parser.parse(str(value))


# ========== GENERIC API CONNECTOR ==========

class GenericAPIConnector:
    """
    Generic connector for ANY JSON API

    Supports:
    - Multiple auth methods (Bearer, Basic, API Key)
    - Multiple pagination types (Offset, Page, None)
    - JSONPath field mapping
    - Data transformations
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector with configuration

        Config structure:
        {
            "api_config": {
                "base_url": "https://api.example.com/changes",
                "method": "GET",
                "auth": {"type": "bearer_token", "token": "xxx"},
                "headers": {"Accept": "application/json"},
                "query_params": {"status": "completed"}
            },
            "pagination": {
                "type": "offset",
                "offset_param": "offset",
                "limit_param": "limit",
                "page_size": 100
            },
            "field_mapping": {
                "change_id": "$.result[*].number",
                "description": "$.result[*].short_description",
                "timestamp": "$.result[*].sys_created_on",
                "service_name": "$.result[*].cmdb_ci.name"
            },
            "transformations": {
                "timestamp": {"type": "datetime", "format": "iso8601"}
            }
        }
        """
        self.config = config
        self.api_config = config['api_config']
        self.base_url = self.api_config['base_url']
        self.method = self.api_config.get('method', 'GET')

        # Create auth handler
        self.auth_handler = AuthHandlerFactory.create(self.api_config['auth'])

        # Create pagination handler
        self.pagination_handler = PaginationHandlerFactory.create(
            config.get('pagination')
        )

        # Create field mapper
        self.field_mapper = FieldMapper(
            config['field_mapping'],
            config.get('transformations')
        )

    def test_connection(self) -> bool:
        """
        Test if connection to ITSM API works

        Returns:
            True if connection successful, False otherwise
        """
        try:
            headers = self.api_config.get('headers', {}).copy()
            headers = self.auth_handler.apply_auth(headers)

            params = self.api_config.get('query_params', {}).copy()
            params = self._replace_template_vars(params, {})

            # Limit to 1 record for test
            if isinstance(self.pagination_handler, OffsetPagination):
                params[self.pagination_handler.limit_param] = 1
            elif isinstance(self.pagination_handler, PagePagination):
                params[self.pagination_handler.per_page_param] = 1

            response = requests.request(
                method=self.method,
                url=self.base_url,
                headers=headers,
                params=params,
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def fetch_changes(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[ChangeEvent]:
        """
        Fetch changes from ITSM API

        Args:
            start_time: Fetch changes from this time
            end_time: Fetch changes until this time

        Returns:
            List of ChangeEvent objects
        """
        logger.info(f"Fetching changes from {start_time} to {end_time}")

        all_records = []
        page_num = 0

        # Template variables for query params
        template_vars = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }

        # Initial params
        params = self.api_config.get('query_params', {}).copy()
        params = self._replace_template_vars(params, template_vars)

        # Paginate
        while True:
            page_num += 1
            logger.debug(f"Fetching page {page_num}: {params}")

            try:
                # Make request
                response = self._make_request(params)

                # Extract records from response
                records = self.field_mapper.extract_fields(response)
                all_records.extend(records)

                logger.info(f"Page {page_num}: extracted {len(records)} records")

                # Check if there's a next page
                next_params = self.pagination_handler.get_next_params(
                    params,
                    response,
                    page_num
                )

                if next_params is None:
                    break  # No more pages

                params = next_params

            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}", exc_info=True)
                break

        logger.info(f"Fetched total {len(all_records)} change records")

        # Convert to ChangeEvent objects
        change_events = []
        for record in all_records:
            try:
                change_event = ChangeEvent(
                    change_id=record['change_id'],
                    change_type=record.get('change_type', 'deployment'),
                    service_name=record.get('service_name'),
                    description=record.get('description'),
                    timestamp=record['timestamp'],
                    metadata=record  # Store full record
                )
                change_events.append(change_event)
            except Exception as e:
                logger.error(f"Error creating ChangeEvent from record: {e}")
                continue

        return change_events

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to API"""
        headers = self.api_config.get('headers', {}).copy()
        headers = self.auth_handler.apply_auth(headers)

        response = requests.request(
            method=self.method,
            url=self.base_url,
            headers=headers,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    def _replace_template_vars(
        self,
        params: Dict[str, Any],
        variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Replace template variables in query params

        Example:
            params = {"filter": "created_at>={start_time}"}
            variables = {"start_time": "2025-01-01T00:00:00Z"}
            result = {"filter": "created_at>=2025-01-01T00:00:00Z"}
        """
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                for var_name, var_value in variables.items():
                    value = value.replace(f"{{{var_name}}}", var_value)
            result[key] = value
        return result
```

## Day 5-6: Correlation Service & Sync Worker

### Task 3.1: Create Change Correlation Service

**File:** `app/services/change_correlation_service.py` (new file)

```python
"""
Change Correlation Service

Analyze correlation between changes and incidents
"""
import logging
import math
from typing import List, Optional, Dict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Alert
from app.models_itsm import ChangeEvent, ChangeImpactAnalysis
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


class ChangeCorrelationService:
    """Correlate changes with incidents"""

    def __init__(self, db: Session):
        self.db = db

    def analyze_change_impact(
        self,
        change: ChangeEvent,
        window_hours: int = 2
    ) -> ChangeImpactAnalysis:
        """
        Analyze impact of a change on incidents

        Args:
            change: ChangeEvent to analyze
            window_hours: Hours after change to look for incidents

        Returns:
            ChangeImpactAnalysis
        """
        window_end = change.timestamp + timedelta(hours=window_hours)

        # Find alerts that occurred after this change
        alerts = self.db.query(Alert).filter(
            Alert.timestamp.between(change.timestamp, window_end),
            Alert.severity.in_(['critical', 'warning'])
        ).all()

        # Calculate correlation score
        correlation_score = self._calculate_correlation_score(change, alerts)

        # Determine impact level
        if correlation_score >= 0.7:
            impact_level = 'high'
            recommendation = "Consider rollback or hotfix"
        elif correlation_score >= 0.4:
            impact_level = 'medium'
            recommendation = "Monitor closely"
        else:
            impact_level = 'low'
            recommendation = None

        # Create impact analysis
        analysis = ChangeImpactAnalysis(
            change_event_id=change.id,
            incidents_after=len(alerts),
            critical_incidents=len([a for a in alerts if a.severity == 'critical']),
            correlation_score=correlation_score,
            impact_level=impact_level,
            recommendation=recommendation
        )

        self.db.add(analysis)
        self.db.commit()

        # Update change event
        change.correlation_score = correlation_score
        change.impact_level = impact_level
        self.db.commit()

        return analysis

    def _calculate_correlation_score(
        self,
        change: ChangeEvent,
        alerts: List[Alert]
    ) -> float:
        """
        Calculate correlation score (0.0 - 1.0)

        Factors:
        - Time proximity (30%)
        - Incident volume (20%)
        - Incident severity (30%)
        - Service match (20%)
        """
        if not alerts:
            return 0.0

        # Factor 1: Time proximity (exponential decay)
        time_deltas = [
            (alert.timestamp - change.timestamp).total_seconds() / 3600
            for alert in alerts
        ]
        avg_time_delta = sum(time_deltas) / len(time_deltas)
        # Decay over 1 hour (closer = higher score)
        time_score = math.exp(-avg_time_delta / 1.0)

        # Factor 2: Incident volume
        # More incidents = higher score (max at 5 incidents)
        volume_score = min(len(alerts) / 5.0, 1.0)

        # Factor 3: Severity
        severity_weights = {'critical': 1.0, 'warning': 0.5, 'info': 0.1}
        severity_scores = [
            severity_weights.get(alert.severity, 0)
            for alert in alerts
        ]
        severity_score = sum(severity_scores) / len(alerts) if alerts else 0

        # Factor 4: Service match
        if change.service_name:
            service_matches = sum(
                1 for alert in alerts
                if change.service_name in str(alert.labels_json.get('service', '')) or
                   change.service_name in str(alert.labels_json.get('job', ''))
            )
            service_score = service_matches / len(alerts) if alerts else 0
        else:
            service_score = 0

        # Weighted combination
        correlation = (
            time_score * 0.3 +
            volume_score * 0.2 +
            severity_score * 0.3 +
            service_score * 0.2
        )

        return round(correlation, 3)

    def get_changes_for_alert(
        self,
        alert: Alert,
        lookback_hours: int = 2
    ) -> List[ChangeEvent]:
        """
        Find changes that occurred before an alert

        Useful for root cause analysis
        """
        lookback_start = alert.timestamp - timedelta(hours=lookback_hours)

        changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp.between(lookback_start, alert.timestamp)
        ).order_by(ChangeEvent.timestamp.desc()).all()

        return changes

    def detect_suspicious_changes(
        self,
        threshold_score: float = 0.7
    ) -> List[ChangeEvent]:
        """
        Find changes with high correlation scores

        Returns:
            List of suspicious changes (score >= threshold)
        """
        changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.correlation_score >= threshold_score
        ).order_by(ChangeEvent.correlation_score.desc()).all()

        return changes
```

### Task 3.2: Create Sync Worker

**File:** `app/services/itsm_sync_worker.py` (new file)

```python
"""
ITSM Sync Background Worker

Periodically fetches changes from ITSM systems
and runs correlation analysis
"""
import logging
import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models_itsm import ITSMIntegration, ChangeEvent
from app.services.itsm_connector import GenericAPIConnector
from app.services.change_correlation_service import ChangeCorrelationService
from app.utils.crypto import decrypt_value
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)


async def sync_itsm_changes():
    """
    Main sync job - runs every 15 minutes

    1. Load enabled integrations
    2. For each integration:
       - Fetch changes since last sync
       - Store as ChangeEvent records
       - Run correlation analysis
    3. Update sync status
    """
    db = SessionLocal()

    try:
        # Get all enabled integrations
        integrations = db.query(ITSMIntegration).filter(
            ITSMIntegration.is_enabled == True
        ).all()

        if not integrations:
            logger.info("No enabled ITSM integrations")
            return

        logger.info(f"Syncing {len(integrations)} ITSM integrations...")

        for integration in integrations:
            try:
                await _sync_integration(db, integration)
            except Exception as e:
                logger.error(f"Failed to sync integration {integration.name}: {e}", exc_info=True)
                # Mark as failed but continue with others
                integration.last_sync = utc_now()
                integration.last_sync_status = 'failed'
                integration.last_error = str(e)
                db.commit()
                continue

        logger.info("✅ ITSM sync complete")

    except Exception as e:
        logger.error(f"ITSM sync failed: {e}", exc_info=True)
    finally:
        db.close()


async def _sync_integration(db: Session, integration: ITSMIntegration):
    """Sync a single ITSM integration"""
    logger.info(f"Syncing {integration.name}...")

    # Decrypt config
    config_json = decrypt_value(integration.config_encrypted)
    config = json.loads(config_json)

    # Create connector
    connector = GenericAPIConnector(config)

    # Determine time range
    if integration.last_sync:
        # Fetch changes since last sync
        start_time = integration.last_sync
    else:
        # First sync - fetch last 24 hours
        start_time = utc_now() - timedelta(hours=24)

    end_time = utc_now()

    # Fetch changes
    logger.info(f"Fetching changes from {start_time} to {end_time}")

    changes = connector.fetch_changes(start_time, end_time)

    logger.info(f"Fetched {len(changes)} changes")

    # Store changes
    new_changes = []
    for change in changes:
        # Check if already exists
        existing = db.query(ChangeEvent).filter(
            ChangeEvent.change_id == change.change_id
        ).first()

        if not existing:
            change.source = str(integration.id)
            db.add(change)
            db.flush()
            new_changes.append(change)
        else:
            logger.debug(f"Change {change.change_id} already exists")

    db.commit()

    logger.info(f"Stored {len(new_changes)} new changes")

    # Run correlation analysis on new changes
    if new_changes:
        correlation_service = ChangeCorrelationService(db)

        for change in new_changes:
            try:
                analysis = correlation_service.analyze_change_impact(change)
                logger.debug(
                    f"Change {change.change_id}: "
                    f"correlation={analysis.correlation_score:.2f}, "
                    f"impact={analysis.impact_level}"
                )
            except Exception as e:
                logger.error(f"Failed to analyze change {change.change_id}: {e}")
                continue

    # Update sync status
    integration.last_sync = end_time
    integration.last_sync_status = 'success'
    integration.last_error = None
    db.commit()

    logger.info(f"✅ {integration.name} synced successfully")


def start_itsm_sync_jobs(scheduler):
    """Register ITSM sync jobs with scheduler"""

    # Sync job - every 15 minutes
    scheduler.add_job(
        sync_itsm_changes,
        'interval',
        minutes=15,
        id='sync_itsm_changes',
        replace_existing=True
    )

    logger.info("✅ ITSM sync jobs registered")
```

**Integration in `app/main.py`:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...

    # Start ITSM sync jobs
    logger.info("Starting ITSM sync background jobs...")
    from app.services.itsm_sync_worker import start_itsm_sync_jobs
    start_itsm_sync_jobs(scheduler)

    yield

    # ... shutdown ...
```

*Due to length limits, the implementation plan continues with Day 7-10 (API Endpoints, Dashboard UI) and testing strategy in the actual file.*

---

# Complete Implementation Plan Available

The complete plan is now saved to: `/home/user/remediation-engine/IMPLEMENTATION_PLAN.md`

**Total Plan Size:** ~4000 lines covering:
- Week 1-2: Alert Clustering (complete)
- Week 3-4: MTTR Deep Dive (complete)
- Week 5-6: Change Correlation (in progress - core implementation complete)

**Remaining sections to add:**
- Week 5-6: API Endpoints & Dashboard UI (Day 7-10)
- Testing Strategy
- Deployment Guide
- Configuration Examples

Would you like me to complete the remaining sections of Week 5-6?
