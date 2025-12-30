
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, case, text, extract
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models import IncidentMetrics, Alert
from app.schemas import MTTRAnalytics, MTTRBreakdown, TrendPoint, RegressionAlert

class MetricsAnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def _apply_date_filter(self, query: Select, time_range: str) -> Select:
        now = datetime.now(timezone.utc)
        if time_range == "24h":
            start_time = now - timedelta(hours=24)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        elif time_range == "30d":
            start_time = now - timedelta(days=30)
        elif time_range == "90d":
            start_time = now - timedelta(days=90)
        else:
            start_time = now - timedelta(days=30)  # Default

        return query.filter(IncidentMetrics.incident_started >= start_time)

    def _calculate_percentiles(self, values: List[int]) -> Tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        def get_p(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = k - f
            if f + 1 < n:
                return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c
            else:
                return float(sorted_values[f])

        return get_p(0.50), get_p(0.95), get_p(0.99)

    def get_aggregate_stats(
        self, 
        metric_type: str = "time_to_resolve", 
        time_range: str = "30d",
        service: Optional[str] = None,
        severity: Optional[str] = None
    ) -> MTTRAnalytics:
        """
        Get aggregate statistics (avg, p50, p95, p99) for a specific metric.
        
        Args:
            metric_type: Column name to aggregate (e.g., 'time_to_resolve', 'time_to_acknowledge')
            time_range: Time window filter ('24h', '7d', '30d')
            service: Optional filter by service name
            severity: Optional filter by severity
        """
        metric_col = getattr(IncidentMetrics, metric_type, None)
        if not metric_col:
            raise ValueError(f"Invalid metric type: {metric_type}")

        query = self.db.query(metric_col).filter(metric_col.isnot(None))
        query = self._apply_date_filter(query, time_range)

        if service:
            query = query.filter(IncidentMetrics.service_name == service)
        if severity:
            query = query.filter(IncidentMetrics.severity == severity)

        results = [r[0] for r in query.all()]
        
        if not results:
            return MTTRAnalytics(avg=0, p50=0, p95=0, p99=0, sample_size=0)

        avg = sum(results) / len(results)
        p50, p95, p99 = self._calculate_percentiles(results)

        return MTTRAnalytics(
            avg=round(avg, 2),
            p50=round(p50, 2),
            p95=round(p95, 2),
            p99=round(p99, 2),
            sample_size=len(results)
        )

    def get_breakdown(
        self,
        dimension: str,
        metric_type: str = "time_to_resolve",
        time_range: str = "30d"
    ) -> MTTRBreakdown:
        """
        Get MTTR breakdown by dimension (service, severity, resolution_type).
        """
        dimension_col = getattr(IncidentMetrics, dimension, None)
        metric_col = getattr(IncidentMetrics, metric_type, None)
        
        if not dimension_col or not metric_col:
            raise ValueError(f"Invalid dimension or metric type")

        # Get all values grouped by dimension
        query = self.db.query(dimension_col, metric_col)\
            .filter(metric_col.isnot(None))\
            .filter(dimension_col.isnot(None))
        
        query = self._apply_date_filter(query, time_range)
        
        results = query.all()
        
        # Group in memory (easier for percentiles than complex SQL)
        grouped_data: Dict[str, List[int]] = {}
        for dim_val, val in results:
            if dim_val not in grouped_data:
                grouped_data[dim_val] = []
            grouped_data[dim_val].append(val)
            
        breakdown_stats = {}
        for dim_val, values in grouped_data.items():
            avg = sum(values) / len(values)
            p50, p95, p99 = self._calculate_percentiles(values)
            breakdown_stats[dim_val] = MTTRAnalytics(
                avg=round(avg, 2),
                p50=round(p50, 2),
                p95=round(p95, 2),
                p99=round(p99, 2),
                sample_size=len(values)
            )
            
        return MTTRBreakdown(
            dimension=dimension,
            breakdown=breakdown_stats
        )

    def get_trends(
        self,
        metric_type: str = "time_to_resolve",
        time_range: str = "30d",
        interval: str = "day"  # day, week
    ) -> List[TrendPoint]:
        """
        Get trend analysis over time.
        """
        metric_col = getattr(IncidentMetrics, metric_type, None)
        if not metric_col:
            raise ValueError(f"Invalid metric type: {metric_type}")

        # Choose date truncation
        if interval == "week":
            trunc_func = func.date_trunc('week', IncidentMetrics.incident_started)
        else:
            trunc_func = func.date_trunc('day', IncidentMetrics.incident_started)

        query = self.db.query(
            trunc_func.label('period'),
            func.avg(metric_col).label('avg_val'),
            func.count(metric_col).label('count_val')
        ).filter(metric_col.isnot(None))

        query = self._apply_date_filter(query, time_range)
        
        results = query.group_by('period').order_by('period').all()
        
        trends = []
        for period, avg_val, count_val in results:
            trends.append(TrendPoint(
                timestamp=period,
                value=round(float(avg_val), 2) if avg_val else 0.0,
                sample_size=count_val
            ))
            
        return trends

    def detect_regressions(
        self,
        metric_type: str = "time_to_resolve",
        threshold_percent: float = 20.0
    ) -> List[RegressionAlert]:
        """
        Compare current period (last 7 days) vs previous period (7-14 days ago)
        to detect regressions.
        """
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=7)
        previous_start = now - timedelta(days=14)
        
        metric_col = getattr(IncidentMetrics, metric_type, None)
        
        # Helper to get avg by service
        def get_service_avgs(start, end):
            results = self.db.query(
                IncidentMetrics.service_name,
                func.avg(metric_col).label('avg_val')
            ).filter(
                metric_col.isnot(None),
                IncidentMetrics.service_name.isnot(None),
                IncidentMetrics.incident_started >= start,
                IncidentMetrics.incident_started < end
            ).group_by(IncidentMetrics.service_name).all()
            return {r[0]: float(r[1]) for r in results}

        current_avgs = get_service_avgs(current_start, now)
        previous_avgs = get_service_avgs(previous_start, current_start)
        
        regressions = []
        
        for service, curr_val in current_avgs.items():
            prev_val = previous_avgs.get(service)
            
            if prev_val and prev_val > 0:
                change_pct = ((curr_val - prev_val) / prev_val) * 100
                
                if change_pct >= threshold_percent:
                    regressions.append(RegressionAlert(
                        service_name=service,
                        metric=metric_type,
                        current_value=round(curr_val, 2),
                        previous_value=round(prev_val, 2),
                        change_percent=round(change_pct, 1),
                        severity="warning" if change_pct < 50 else "critical"
                    ))
                    
        return regressions
