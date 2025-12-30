# Prometheus Dashboard Builder - Current Status

## ✅ Completed

### 1. Database Schema (100%)
- **File:** `app/models_dashboards.py`
- **Models Created:**
  - `PrometheusDatasource` - Multi-Prometheus server support
  - `PrometheusPanel` - Saved graph/visualization configurations
  - `Dashboard` - Custom dashboard metadata
  - `DashboardPanel` - Junction table for dashboard ↔ panel

- **Migration:** `alembic/versions/023_add_prometheus_dashboards.py`

### 2. Documentation (100%)
- **File:** `docs/PROMETHEUS_DASHBOARD_BUILDER.md` (500+ lines)
- Complete architecture overview
- Database schema documentation
- API endpoint specifications (30+ endpoints)
- UI component wireframes
- Implementation workflow
- Example queries and templates

### 3. Configuration (100%)
- Configurable Prometheus settings already in place
- Support for multiple datasources in schema

---

## 🚧 To Be Implemented

### Phase 1: Backend APIs (Estimated: 2-3 days)

#### 1.1 Datasource Management API
**File:** `app/routers/datasources_api.py` (create)

```python
GET    /api/datasources              # List all
GET    /api/datasources/{id}          # Get one
POST   /api/datasources              # Create
PUT    /api/datasources/{id}          # Update
DELETE /api/datasources/{id}          # Delete
POST   /api/datasources/{id}/test    # Test connection
```

**Implementation:**
- CRUD operations
- Password encryption (use existing Fernet from credentials)
- Connection testing
- Default datasource management

#### 1.2 Panel Management API
**File:** `app/routers/panels_api.py` (create)

```python
GET    /api/panels                    # List with filters
GET    /api/panels/{id}              # Get one
POST   /api/panels                    # Create
PUT    /api/panels/{id}              # Update
DELETE /api/panels/{id}              # Delete
POST   /api/panels/test-query        # Test PromQL
GET    /api/panels/{id}/data         # Get panel data
```

**Implementation:**
- CRUD operations
- Query validation
- Data fetching from Prometheus
- Tag-based filtering

#### 1.3 Dashboard Management API
**File:** `app/routers/dashboards_api.py` (create)

```python
GET    /api/dashboards                              # List
GET    /api/dashboards/{id}                        # Get full dashboard
POST   /api/dashboards                              # Create
PUT    /api/dashboards/{id}                        # Update
DELETE /api/dashboards/{id}                        # Delete
POST   /api/dashboards/{id}/panels                # Add panel
DELETE /api/dashboards/{dashboard_id}/panels/{panel_id}  # Remove
PUT    /api/dashboards/{dashboard_id}/panels/{panel_id}/position  # Move
POST   /api/dashboards/{id}/clone                 # Clone
```

**Implementation:**
- CRUD operations
- Panel association
- Layout management
- Dashboard cloning

---

### Phase 2: Frontend UI (Estimated: 3-4 days)

#### 2.1 Datasource Management Page
**File:** `templates/datasources.html` (create)

**Features:**
- Table view of all datasources
- Add/Edit modal forms
- Test connection button with live status
- Set default datasource
- Delete confirmation

**Components:**
- List table with status indicators
- Modal for add/edit
- Connection test with loading spinner

#### 2.2 Panel Builder
**File:** `templates/panel_builder.html` (create)

**Features:**
- PromQL editor with syntax highlighting
- Query testing and validation
- Live preview of results
- Visualization type selector
- Threshold configuration
- Tags and metadata

**Libraries:**
- CodeMirror for PromQL editing
- ECharts for live preview
- Form validation

#### 2.3 Dashboard Builder
**File:** `templates/dashboard_builder.html` (create)

**Features:**
- Drag-and-drop grid layout
- Panel selector (existing panels)
- Inline panel creation
- Resize and reposition
- Global settings (time range, refresh)
- Save/load dashboards

**Libraries:**
- GridStack.js for grid layout
- ECharts for panels
- Drag-drop API

#### 2.4 Dashboard View
**File:** `templates/dashboard_view.html` (create)

**Features:**
- Render dashboard with all panels
- Time range picker
- Auto-refresh toggle
- Full-screen mode
- Edit dashboard button
- Share dashboard

---

### Phase 3: Advanced Features (Estimated: 2-3 days)

#### 3.1 Panel Templates
**File:** `app/services/panel_templates.py` (create)

Pre-built templates:
- Node CPU usage
- Memory usage
- Disk I/O
- Network traffic
- HTTP request rates
- Error rates
- Latency percentiles

#### 3.2 Query Builder (Optional)
**File:** `templates/query_builder.html` (create)

Visual query builder for users unfamiliar with PromQL:
- Metric selector dropdown
- Label filters
- Function selector (rate, sum, avg, etc.)
- Generates PromQL automatically

#### 3.3 Dashboard Variables (Advanced)
Dynamic variables for dashboards:
- Instance selector
- Environment selector
- Custom variables from queries

---

## Quick Start Implementation

### Step 1: Run Migration

```bash
alembic upgrade head
```

This creates all 4 new tables.

### Step 2: Import Models

Add to `app/main.py`:

```python
import app.models_dashboards  # noqa: F401
```

### Step 3: Register Routers (when created)

Add to `app/main.py`:

```python
from app.routers import datasources_api, panels_api, dashboards_api

app.include_router(datasources_api.router)
app.include_router(panels_api.router)
app.include_router(dashboards_api.router)
```

### Step 4: Create Default Datasource (optional)

Add to `app/main.py` init_db():

```python
from app.models_dashboards import PrometheusDatasource

# Check if default datasource exists
default_ds = db.query(PrometheusDatasource).filter_by(is_default=True).first()
if not default_ds:
    ds = PrometheusDatasource(
        name="Default Prometheus",
        url=settings.prometheus_url,
        is_default=True,
        is_enabled=True
    )
    db.add(ds)
    db.commit()
```

---

## Minimal Implementation (1-2 days)

If you want to start with just the essentials:

### Must Have:
1. ✅ Database models (done)
2. Datasource API (basic CRUD)
3. Panel API (basic CRUD + query execution)
4. Dashboard API (basic CRUD)
5. Simple datasource list page
6. Simple panel creator with PromQL textarea
7. Simple dashboard view (no drag-drop, just list panels)

### Can Skip Initially:
- Advanced query builder
- Dashboard variables
- Annotations
- Alerting from panels
- Dashboard snapshots
- Panel templates (use manual queries)

---

## API Implementation Priority

### Priority 1 (Core Functionality)
1. POST /api/datasources (create)
2. GET /api/datasources (list)
3. POST /api/panels (create)
4. POST /api/panels/test-query (validate queries)
5. GET /api/panels/{id}/data (fetch data)
6. POST /api/dashboards (create)
7. POST /api/dashboards/{id}/panels (add panel to dashboard)
8. GET /api/dashboards/{id} (view dashboard with all panels)

### Priority 2 (Management)
9. PUT /api/datasources/{id} (update)
10. DELETE /api/datasources/{id} (delete)
11. PUT /api/panels/{id} (update)
12. DELETE /api/panels/{id} (delete)
13. PUT /api/dashboards/{id} (update)
14. DELETE /api/dashboards/{id} (delete)

### Priority 3 (Advanced)
15. POST /api/datasources/{id}/test (test connection)
16. PUT /api/dashboards/{dashboard_id}/panels/{panel_id}/position (move panels)
17. POST /api/dashboards/{id}/clone (clone dashboard)
18. GET /api/panels (list with search/filters)

---

## Example: Simple Panel Creation

**Minimal API:**

```python
# app/routers/panels_api.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models_dashboards import PrometheusPanel, PrometheusDatasource
from app.services.prometheus_service import PrometheusClient
from pydantic import BaseModel

router = APIRouter(prefix="/api/panels", tags=["Panels"])

class PanelCreate(BaseModel):
    name: str
    datasource_id: str
    promql_query: str
    panel_type: str = "graph"
    time_range: str = "24h"

@router.post("/")
async def create_panel(panel: PanelCreate, db: Session = Depends(get_db)):
    new_panel = PrometheusPanel(
        name=panel.name,
        datasource_id=panel.datasource_id,
        promql_query=panel.promql_query,
        panel_type=panel.panel_type,
        time_range=panel.time_range
    )
    db.add(new_panel)
    db.commit()
    db.refresh(new_panel)
    return new_panel

@router.get("/{panel_id}/data")
async def get_panel_data(panel_id: str, db: Session = Depends(get_db)):
    panel = db.query(PrometheusPanel).filter_by(id=panel_id).first()
    datasource = db.query(PrometheusDatasource).filter_by(id=panel.datasource_id).first()

    # Query Prometheus
    client = PrometheusClient(datasource.url)
    # ... fetch and return data
```

**Minimal UI:**

```html
<!-- templates/panel_create.html -->
<form method="POST" action="/api/panels">
  <input name="name" placeholder="Panel Name" required>

  <select name="datasource_id">
    {% for ds in datasources %}
    <option value="{{ds.id}}">{{ds.name}}</option>
    {% endfor %}
  </select>

  <textarea name="promql_query" placeholder="Enter PromQL query" rows="5"></textarea>

  <select name="panel_type">
    <option value="graph">Graph</option>
    <option value="stat">Stat</option>
    <option value="gauge">Gauge</option>
  </select>

  <button type="submit">Create Panel</button>
</form>
```

---

## Estimated Effort

| Component | Complexity | Time Estimate |
|-----------|-----------|---------------|
| Database migrations | ✅ Done | - |
| Datasource API | Low | 4 hours |
| Panel API | Medium | 8 hours |
| Dashboard API | Medium | 8 hours |
| Datasource UI | Low | 4 hours |
| Panel Builder UI | High | 16 hours |
| Dashboard Builder UI | High | 24 hours |
| Testing & Polish | Medium | 8 hours |
| **TOTAL** | | **~72 hours (9 days)** |

**Minimal Version:** ~24 hours (3 days) with basic UI

---

## What You Have Now

✅ **Complete database schema** - Ready to use
✅ **Comprehensive documentation** - 500+ lines
✅ **Clear implementation roadmap** - Step-by-step guide
✅ **Architecture designed** - Grafana-inspired

## What You Need

🔨 **Implement the APIs** - Following the guide
🎨 **Build the UI** - Following the wireframes
🧪 **Test the integration** - Ensure everything works

---

## Next Steps

1. **Option A:** Continue implementation now
   - I can implement the core APIs
   - I can build the basic UI
   - We can iterate on features

2. **Option B:** Implement yourself
   - Use the comprehensive guide
   - Start with minimal version (3 days)
   - Expand to full version (9 days)

3. **Option C:** Hybrid approach
   - I implement backend APIs (1 day)
   - You implement frontend UI
   - We integrate together

**Which approach would you prefer?**
