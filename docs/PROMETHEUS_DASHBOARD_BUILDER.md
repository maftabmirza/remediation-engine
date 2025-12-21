# Prometheus Dashboard Builder - Implementation Guide

This document outlines the implementation of a Grafana-like dashboard builder integrated into the AIOps platform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard Builder UI                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Datasources │  │    Panels    │  │  Dashboards  │      │
│  │  Management  │  │   Builder    │  │   Composer   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Datasource  │  │    Panel     │  │  Dashboard   │      │
│  │     API      │  │     API      │  │     API      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                      │
│  • prometheus_datasources                                    │
│  • prometheus_panels                                         │
│  • dashboards                                               │
│  • dashboard_panels                                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Multiple Prometheus Instances                   │
│  • Production Prometheus                                     │
│  • Development Prometheus                                    │
│  • Regional Prometheus Servers                              │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### 1. `prometheus_datasources`
Stores multiple Prometheus server configurations.

```sql
CREATE TABLE prometheus_datasources (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    url VARCHAR(512) NOT NULL,
    description TEXT,
    auth_type VARCHAR(50) DEFAULT 'none',
    username VARCHAR(255),
    password VARCHAR(512),  -- encrypted
    bearer_token VARCHAR(512),  -- encrypted
    timeout INTEGER DEFAULT 30,
    is_default BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    custom_headers JSON,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255)
);
```

### 2. `prometheus_panels`
Stores individual graph/visualization configurations.

```sql
CREATE TABLE prometheus_panels (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    datasource_id VARCHAR(36) REFERENCES prometheus_datasources(id),
    promql_query TEXT NOT NULL,
    legend_format VARCHAR(255),
    time_range VARCHAR(50) DEFAULT '24h',
    refresh_interval INTEGER DEFAULT 30,
    step VARCHAR(20) DEFAULT 'auto',
    panel_type ENUM('graph', 'gauge', 'stat', 'table', 'heatmap', 'bar', 'pie'),
    visualization_config JSON,
    thresholds JSON,
    tags JSON,
    is_public BOOLEAN DEFAULT FALSE,
    is_template BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255)
);
```

### 3. `dashboards`
Stores dashboard metadata and layout.

```sql
CREATE TABLE dashboards (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    layout JSON,  -- Grid layout configuration
    time_range VARCHAR(50) DEFAULT '24h',
    refresh_interval INTEGER DEFAULT 60,
    auto_refresh BOOLEAN DEFAULT TRUE,
    tags JSON,
    folder VARCHAR(255),
    is_public BOOLEAN DEFAULT FALSE,
    is_favorite BOOLEAN DEFAULT FALSE,
    is_home BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255)
);
```

### 4. `dashboard_panels`
Junction table linking dashboards and panels.

```sql
CREATE TABLE dashboard_panels (
    id VARCHAR(36) PRIMARY KEY,
    dashboard_id VARCHAR(36) REFERENCES dashboards(id) ON DELETE CASCADE,
    panel_id VARCHAR(36) REFERENCES prometheus_panels(id) ON DELETE CASCADE,
    grid_x INTEGER DEFAULT 0,
    grid_y INTEGER DEFAULT 0,
    grid_width INTEGER DEFAULT 6,
    grid_height INTEGER DEFAULT 4,
    override_time_range VARCHAR(50),
    override_refresh_interval INTEGER,
    display_order INTEGER DEFAULT 0
);
```

---

## API Endpoints

### Datasource Management

#### List Data Sources
```http
GET /api/datasources
Response: [{id, name, url, is_default, is_enabled, created_at}]
```

#### Get Datasource
```http
GET /api/datasources/{id}
Response: {full datasource object}
```

#### Create Datasource
```http
POST /api/datasources
Body: {name, url, auth_type, username, password, timeout, custom_headers}
Response: {created datasource}
```

#### Update Datasource
```http
PUT /api/datasources/{id}
Body: {name, url, ...}
Response: {updated datasource}
```

#### Delete Datasource
```http
DELETE /api/datasources/{id}
Response: {message: "Datasource deleted"}
```

#### Test Datasource Connection
```http
POST /api/datasources/{id}/test
Response: {status: "ok|error", message, version, targets_count}
```

---

### Panel Management

#### List Panels
```http
GET /api/panels?tags=infrastructure&search=cpu
Response: [{id, name, panel_type, datasource_name, created_at}]
```

#### Get Panel
```http
GET /api/panels/{id}
Response: {full panel configuration}
```

#### Create Panel
```http
POST /api/panels
Body: {
    name, description, datasource_id,
    promql_query, legend_format,
    panel_type, visualization_config, thresholds,
    time_range, refresh_interval, tags
}
Response: {created panel}
```

#### Update Panel
```http
PUT /api/panels/{id}
Body: {panel configuration}
Response: {updated panel}
```

#### Delete Panel
```http
DELETE /api/panels/{id}
Response: {message: "Panel deleted"}
```

#### Test Panel Query
```http
POST /api/panels/test-query
Body: {datasource_id, promql_query, time_range}
Response: {status, data, series_count, sample_data}
```

#### Get Panel Data
```http
GET /api/panels/{id}/data?start=timestamp&end=timestamp
Response: {timestamps[], series: [{name, values[]}]}
```

---

### Dashboard Management

#### List Dashboards
```http
GET /api/dashboards?folder=infrastructure&tags=production
Response: [{id, name, folder, tags, panel_count, is_favorite}]
```

#### Get Dashboard
```http
GET /api/dashboards/{id}
Response: {
    id, name, description, layout,
    panels: [{panel_id, panel_config, grid_position}],
    time_range, refresh_interval
}
```

#### Create Dashboard
```http
POST /api/dashboards
Body: {name, description, time_range, folder, tags}
Response: {created dashboard}
```

#### Update Dashboard
```http
PUT /api/dashboards/{id}
Body: {name, description, layout}
Response: {updated dashboard}
```

#### Delete Dashboard
```http
DELETE /api/dashboards/{id}
Response: {message: "Dashboard deleted"}
```

#### Add Panel to Dashboard
```http
POST /api/dashboards/{id}/panels
Body: {panel_id, grid_x, grid_y, grid_width, grid_height}
Response: {dashboard_panel}
```

#### Remove Panel from Dashboard
```http
DELETE /api/dashboards/{dashboard_id}/panels/{panel_id}
Response: {message: "Panel removed"}
```

#### Update Panel Position
```http
PUT /api/dashboards/{dashboard_id}/panels/{panel_id}/position
Body: {grid_x, grid_y, grid_width, grid_height}
Response: {updated dashboard_panel}
```

#### Clone Dashboard
```http
POST /api/dashboards/{id}/clone
Body: {new_name}
Response: {cloned dashboard}
```

---

## UI Components

### 1. Data Sources Page (`/datasources`)

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Prometheus Data Sources                + Add New  │
├─────────────────────────────────────────────────────┤
│  Name           URL                    Status       │
│  ─────────────────────────────────────────────────  │
│  🟢 Production  http://prom.prod.io    Connected    │
│  🟢 Dev         http://prom.dev.io     Connected    │
│  🔴 Regional    http://prom.eu.io      Offline      │
└─────────────────────────────────────────────────────┘
```

**Features:**
- List all datasources with status indicators
- Add/Edit/Delete datasources
- Test connection button
- Set default datasource
- Configure authentication (basic, bearer token)

### 2. Panel Builder (`/panels/new`)

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Create Panel                              [Save]   │
├─────────────────────────────────────────────────────┤
│  Panel Name: [CPU Usage by Instance___________]    │
│  Datasource:  [Production Prometheus ▼]            │
├─────────────────────────────────────────────────────┤
│  PromQL Query:                          [Run Query] │
│  ┌─────────────────────────────────────────────┐   │
│  │ rate(node_cpu_seconds_total[5m]) * 100      │   │
│  │                                              │   │
│  └─────────────────────────────────────────────┘   │
│  Legend: [{{instance}} - CPU_____________]          │
├─────────────────────────────────────────────────────┤
│  Visualization                                      │
│  Type: [Graph ▼]  Time Range: [24h ▼]             │
│                                                      │
│  Preview:                                           │
│  ┌─────────────────────────────────────────────┐   │
│  │          [Live Chart Preview]                │   │
│  │                                              │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Thresholds:                                        │
│  Warning:  [75___] %    Color: [Yellow]            │
│  Critical: [90___] %    Color: [Red]               │
└─────────────────────────────────────────────────────┘
```

**Features:**
- PromQL editor with syntax highlighting
- Query validation and testing
- Live preview of results
- Multiple visualization types (graph, gauge, stat, table)
- Threshold configuration
- Legend format with template variables
- Save as template option

### 3. Dashboard Builder (`/dashboards/new`)

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Dashboard: Infrastructure Overview     [Save]      │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐   [+ Add Panel ▼]                │
│  │ Settings     │   • Add Existing Panel            │
│  │ • Name       │   • Create New Panel              │
│  │ • Folder     │   • Add Row                       │
│  │ • Tags       │                                    │
│  │ • Time Range │                                    │
│  └──────────────┘                                    │
├─────────────────────────────────────────────────────┤
│  Grid (12 columns):                                 │
│  ┌───────────────┬───────────────┐                 │
│  │  CPU Usage    │  Memory Usage │ ◀ Drag to move  │
│  │  [Graph]      │  [Graph]      │ ⇲ Drag to resize│
│  └───────────────┴───────────────┘                 │
│  ┌──────────────────────────────┐                  │
│  │  Network Traffic             │                  │
│  │  [Line Chart]                │                  │
│  └──────────────────────────────┘                  │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┐            │
│  │Req/s│Err/s│P95  │P99  │ 5xx │ 2xx │            │
│  │[Stat][Stat][Stat][Stat][Stat][Stat]            │
│  └─────┴─────┴─────┴─────┴─────┴─────┘            │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Drag-and-drop grid layout
- Add existing panels or create new ones inline
- Resize and reposition panels
- Global time range picker
- Auto-refresh toggle
- Dashboard variables (coming soon)
- Export/import dashboards (JSON)

---

## Implementation Steps

### Step 1: Backend Implementation

**File: `app/routers/datasources.py`**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models_dashboards import PrometheusDatasource
from app.services.prometheus_service import PrometheusClient

router = APIRouter(prefix="/api/datasources", tags=["Datasources"])

@router.get("/")
async def list_datasources(db: Session = Depends(get_db)):
    return db.query(PrometheusDatasource).all()

@router.post("/")
async def create_datasource(datasource: DatasourceCreate, db: Session = Depends(get_db)):
    # Create and save datasource
    pass

@router.post("/{id}/test")
async def test_datasource(id: str, db: Session = Depends(get_db)):
    datasource = db.query(PrometheusDatasource).filter_by(id=id).first()
    client = PrometheusClient(datasource.url, datasource.timeout)
    # Test connection
    pass
```

**Similar files:**
- `app/routers/panels_api.py`
- `app/routers/dashboards_api.py`

### Step 2: Frontend Implementation

**File: `templates/datasources.html`**
- List view with table
- Add/Edit modal
- Test connection button
- Status indicators

**File: `templates/panel_builder.html`**
- PromQL editor (use CodeMirror or Monaco Editor)
- Query execution and preview
- Visualization selector
- Threshold configuration

**File: `templates/dashboard_builder.html`**
- Grid layout system (use GridStack.js or React Grid Layout)
- Panel selector
- Drag-and-drop interface
- Time range picker

### Step 3: Panel Templates

Create pre-built templates for common use cases:

**Templates:**
1. **Node CPU Usage**
   ```promql
   100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
   ```

2. **Memory Usage**
   ```promql
   (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
   ```

3. **HTTP Request Rate**
   ```promql
   sum(rate(http_requests_total[5m])) by (status_code)
   ```

4. **Error Rate**
   ```promql
   sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
   ```

---

## Advanced Features

### 1. Dashboard Variables
Allow dynamic dashboards with variable substitution:

```
Variable: $instance
Values: Query(label_values(node_cpu_seconds_total, instance))
Usage in Query: node_cpu_seconds_total{instance="$instance"}
```

### 2. Annotations
Mark events on graphs:

```sql
CREATE TABLE dashboard_annotations (
    id VARCHAR(36) PRIMARY KEY,
    dashboard_id VARCHAR(36),
    timestamp TIMESTAMP,
    title VARCHAR(255),
    description TEXT,
    tags JSON
);
```

### 3. Alerting Rules
Create alerts from panels:

```sql
CREATE TABLE panel_alerts (
    id VARCHAR(36) PRIMARY KEY,
    panel_id VARCHAR(36),
    condition VARCHAR(255),  -- "value > threshold"
    threshold FLOAT,
    duration VARCHAR(50),  -- "5m"
    notify_channels JSON
);
```

### 4. Dashboard Snapshots
Save and share dashboard states:

```http
POST /api/dashboards/{id}/snapshot
Response: {snapshot_url, expires_at}
```

---

## Example Workflow

### Creating a Custom Dashboard

1. **Add Prometheus Datasource**
   ```
   Navigate to /datasources
   Click "Add New"
   Enter: Name="Production", URL="http://prom.prod:9090"
   Click "Test & Save"
   ```

2. **Create CPU Panel**
   ```
   Navigate to /panels/new
   Name: "CPU Usage by Server"
   Datasource: "Production"
   Query: rate(node_cpu_seconds_total{mode!="idle"}[5m]) * 100
   Legend: {{instance}}
   Type: Graph
   Threshold: Warning=75, Critical=90
   Click "Save"
   ```

3. **Create Memory Panel**
   ```
   Similar to step 2
   Query: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
   ```

4. **Build Dashboard**
   ```
   Navigate to /dashboards/new
   Name: "Infrastructure Overview"
   Click "Add Panel" → Select "CPU Usage by Server"
   Position: Top-left, 6 columns wide
   Click "Add Panel" → Select "Memory Usage"
   Position: Top-right, 6 columns wide
   Click "Save Dashboard"
   ```

5. **View Dashboard**
   ```
   Navigate to /dashboards/{id}
   See both panels updating in real-time
   Use time range picker: Last 7 days
   Toggle auto-refresh: Every 60 seconds
   ```

---

## Next Steps

1. Implement datasource CRUD API ✅ (models created)
2. Implement panel CRUD API (in progress)
3. Implement dashboard CRUD API
4. Build datasource management UI
5. Build panel builder UI with PromQL editor
6. Build dashboard builder UI with grid layout
7. Add panel templates library
8. Add dashboard import/export
9. Add dashboard variables
10. Add alerting integration

---

## Technologies Used

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL
- **PromQL Editor:** CodeMirror with PromQL mode
- **Charts:** Apache ECharts
- **Grid Layout:** GridStack.js or CSS Grid
- **Authentication:** Existing JWT system
- **Encryption:** Fernet (for credentials)

---

## Benefits Over Current Implementation

| Feature | Before | After |
|---------|--------|-------|
| Prometheus Servers | 1 hardcoded | Unlimited, configurable |
| Queries | Fixed | Custom PromQL queries |
| Panels | 2 hardcoded | Unlimited, saved panels |
| Dashboards | 1 hardcoded | Unlimited, custom dashboards |
| Reusability | None | Panels reusable across dashboards |
| Sharing | No | Public dashboards & panels |
| Flexibility | Low | Grafana-level flexibility |

---

This creates a **complete Grafana-like experience** inside your AIOps platform!
