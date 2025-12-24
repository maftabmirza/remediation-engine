# Grafana Integration Plan
## Hybrid Architecture Strategy

**Document Version:** 1.0
**Date:** 2025-01-01
**Branch:** claude/grafana-integration-dKuiI
**Status:** Planning Phase

---

## Executive Summary

This document outlines the strategic plan to integrate Grafana OSS into the AIOps platform using a **hybrid architecture**. Instead of rebuilding features that already exist in Grafana, we'll:

1. **KEEP** our custom-built dashboard features (Prometheus, playlists, snapshots, permissions)
2. **ADD** Grafana via iframe embedding for missing capabilities (Loki, Tempo, Mimir, SQL, advanced visualizations)
3. **ENSURE** transparent user experience through SSO and unified UI

**Cost Savings:** ~176 hours of development ($17,600-$35,200)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Feature Decision Matrix](#feature-decision-matrix)
3. [User Experience Design](#user-experience-design)
4. [Technical Implementation](#technical-implementation)
5. [Implementation Phases](#implementation-phases)
6. [Deployment Strategy](#deployment-strategy)
7. [Testing & Validation](#testing-validation)
8. [Success Metrics](#success-metrics)

---

## 1. Architecture Overview

### Current State
```
┌─────────────────────────────────────────────┐
│         AIOps Platform (FastAPI)            │
├─────────────────────────────────────────────┤
│ • Prometheus Dashboards (GridStack)         │
│ • Custom Variables & Templating             │
│ • Playlists with Auto-rotation              │
│ • Snapshots (point-in-time)                 │
│ • Panel Rows                                │
│ • Dashboard Permissions                     │
│ • Query History                             │
│ • Tags & Search                             │
└─────────────────────────────────────────────┘
         ↓
    Prometheus (Metrics Only)
```

### Target Hybrid State
```
┌──────────────────────────────────────────────────────────────┐
│              AIOps Platform (FastAPI)                        │
│  ┌────────────────────┐  ┌───────────────────────────────┐  │
│  │  Custom Features   │  │   Grafana OSS (Embedded)      │  │
│  ├────────────────────┤  ├───────────────────────────────┤  │
│  │ • Prometheus       │  │ • Loki (Logs)                 │  │
│  │   Dashboards       │  │ • Tempo (Traces)              │  │
│  │ • Variables +      │  │ • Mimir (Long-term)           │  │
│  │   Chaining         │  │ • Alertmanager (Alerts)       │  │
│  │ • Playlists        │  │ • SQL Datasources             │  │
│  │ • Snapshots        │  │ • Advanced Visualizations     │  │
│  │ • Permissions      │  │ • Built-in Dashboards         │  │
│  │ • Query History    │  │ • Explore UI                  │  │
│  └────────────────────┘  └───────────────────────────────┘  │
│              ↓ SSO/Auth Proxy ↓                              │
└──────────────────────────────────────────────────────────────┘
         ↓                           ↓
    Prometheus              LGTM Stack (Loki, Grafana,
                            Tempo, Mimir, Alertmanager)
```

### Integration Pattern: SSO-Enabled iframe Embedding

**Key Components:**
1. **Authentication Proxy:** FastAPI middleware passes user identity to Grafana
2. **iframe Embedding:** Grafana UI embedded in AIOps templates
3. **Datasource Provisioning:** Auto-configure Grafana datasources
4. **Unified Navigation:** Single menu controls both custom and Grafana features

---

## 2. Feature Decision Matrix

### Features to KEEP (Custom Implementation)

| Feature | Reason to Keep | Status |
|---------|---------------|--------|
| **Prometheus Dashboards** | Already built, GridStack integration, custom panel types | ✅ Complete |
| **Template Variables** | Custom chaining logic (`depends_on`), deep integration | ✅ Complete |
| **Playlists** | Custom auto-rotation, kiosk mode integration | ✅ Complete |
| **Snapshots** | Point-in-time captures, custom storage | ✅ Complete |
| **Panel Rows** | Custom collapse/expand, GridStack layout | ✅ Complete |
| **Permissions** | Fine-grained ACLs, per-user/role | ✅ Complete |
| **Query History** | User-specific tracking, favorites | ✅ Complete |
| **Dashboard Tags** | Custom filtering, search integration | ✅ Complete |
| **Annotations** | Custom event tracking | ✅ Complete |
| **Alert Integration** | Deep integration with runbooks/remediation | ✅ Complete |

### Features to ADD via Grafana (iframe)

| Feature | Datasource | Why Grafana | Estimated Build Time Saved |
|---------|-----------|-------------|---------------------------|
| **Log Analytics** | Loki | LogQL query language, log streaming | 60 hours |
| **Distributed Tracing** | Tempo | TraceQL, span analysis, service graphs | 80 hours |
| **Long-term Metrics** | Mimir | Prometheus at scale, unlimited retention | 40 hours |
| **Alert Visualization** | Alertmanager | Alert grouping, silencing UI | 20 hours |
| **SQL Dashboards** | PostgreSQL/MySQL | Native SQL query builder | 15 hours |
| **Advanced Visualizations** | Multiple | Heatmaps, node graphs, flame graphs | 25 hours |
| **Pre-built Dashboards** | Multiple | Community dashboards, JSON import | N/A |

**Total Time Saved:** ~240 hours
**Integration Effort:** ~44 hours
**Net Savings:** ~196 hours

---

## 3. User Experience Design

### Navigation Structure

```
AIOps Platform
├── 📊 Dashboards (Custom Builder)
│   ├── Create New
│   ├── My Dashboards
│   ├── Shared Dashboards
│   └── Playlists
│
├── 📈 Metrics (Custom)
│   ├── Prometheus Dashboards
│   └── Query History
│
├── 📋 Logs (Grafana iframe)
│   ├── Loki Explore
│   └── Log Dashboards
│
├── 🔍 Traces (Grafana iframe)
│   ├── Tempo Explore
│   └── Service Maps
│
├── 🔔 Alerts (Grafana iframe)
│   ├── Alertmanager
│   └── Alert History
│
├── 💾 Snapshots (Custom)
│   └── Saved Snapshots
│
└── ⚙️ Advanced (Grafana iframe)
    ├── SQL Dashboards
    ├── Custom Grafana Dashboards
    └── Community Dashboards
```

### Transparent User Experience

**User Journey Example:**
```
1. User logs into AIOps (JWT authentication)
   → Session established

2. User clicks "Dashboards"
   → Sees custom GridStack dashboard builder
   → Full editing capabilities, variables, panels

3. User clicks "Logs" in sidebar
   → Seamlessly transitions to Grafana's Loki Explore
   → NO separate login required (SSO)
   → Same theme, same navigation
   → User cannot tell it's an iframe

4. User clicks "Traces"
   → Grafana's Tempo UI appears
   → Same seamless experience

5. User clicks back to "Dashboards"
   → Returns to custom builder
   → All state preserved
```

**Transparency Techniques:**

1. **Single Sign-On (SSO)**
   ```python
   # FastAPI passes user to Grafana
   headers = {"X-WEBAUTH-USER": current_user.username}
   # Grafana auto-provisions user, no login needed
   ```

2. **Frameless iframe**
   ```html
   <iframe src="/grafana/..."
     frameborder="0"
     style="border: none; width: 100%; height: 100%">
   </iframe>
   ```

3. **Unified Theme**
   ```yaml
   # Grafana matches AIOps theme
   GF_DEFAULT_THEME: "dark"
   GF_UI_THEME_JSON: |
     {"colors": {"primary": "#1f77b4", ...}}
   ```

4. **URL Routing**
   ```
   aiops.example.com/dashboards    → Custom builder
   aiops.example.com/logs          → Grafana Loki (proxied)
   aiops.example.com/traces        → Grafana Tempo (proxied)
   ```

---

## 4. Technical Implementation

### 4.1 Docker Compose Configuration

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  # Existing services...

  grafana:
    image: grafana/grafana-enterprise:latest
    container_name: aiops-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      # SSO Configuration
      - GF_AUTH_PROXY_ENABLED=true
      - GF_AUTH_PROXY_HEADER_NAME=X-WEBAUTH-USER
      - GF_AUTH_PROXY_HEADER_PROPERTY=username
      - GF_AUTH_PROXY_AUTO_SIGN_UP=true
      - GF_AUTH_PROXY_ENABLE_LOGIN_TOKEN=false

      # Server Configuration
      - GF_SERVER_ROOT_URL=http://localhost:8000/grafana
      - GF_SERVER_SERVE_FROM_SUB_PATH=true

      # Security
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_SECURITY_ALLOW_EMBEDDING=true
      - GF_AUTH_ANONYMOUS_ENABLED=false

      # Theme
      - GF_DEFAULT_THEME=dark

      # Disable Grafana's own login
      - GF_AUTH_DISABLE_LOGIN_FORM=true
      - GF_AUTH_DISABLE_SIGNOUT_MENU=true

    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    networks:
      - aiops-network
    depends_on:
      - loki
      - tempo
      - mimir
      - alertmanager

  loki:
    image: grafana/loki:latest
    container_name: aiops-loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - loki-data:/loki
    networks:
      - aiops-network

  tempo:
    image: grafana/tempo:latest
    container_name: aiops-tempo
    ports:
      - "3200:3200"
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP
    command: -config.file=/etc/tempo/tempo.yaml
    volumes:
      - tempo-data:/var/tempo
      - ./tempo/tempo.yaml:/etc/tempo/tempo.yaml
    networks:
      - aiops-network

  mimir:
    image: grafana/mimir:latest
    container_name: aiops-mimir
    ports:
      - "9009:9009"
    command: -config.file=/etc/mimir/mimir.yaml
    volumes:
      - mimir-data:/data
      - ./mimir/mimir.yaml:/etc/mimir/mimir.yaml
    networks:
      - aiops-network

  alertmanager:
    image: prom/alertmanager:latest
    container_name: aiops-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - alertmanager-data:/alertmanager
      - ./alertmanager/config.yml:/etc/alertmanager/config.yml
    networks:
      - aiops-network

volumes:
  grafana-data:
  loki-data:
  tempo-data:
  mimir-data:
  alertmanager-data:

networks:
  aiops-network:
    driver: bridge
```

### 4.2 Grafana Datasource Provisioning

**File:** `grafana/provisioning/datasources/datasources.yml`

```yaml
apiVersion: 1

datasources:
  # Prometheus (existing)
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 5s
      queryTimeout: 60s

  # Loki for logs
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
    jsonData:
      maxLines: 1000

  # Tempo for traces
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    editable: false
    jsonData:
      tracesToLogs:
        datasourceUid: loki
        tags: ['job', 'instance', 'pod', 'namespace']
      tracesToMetrics:
        datasourceUid: prometheus
      serviceMap:
        datasourceUid: prometheus

  # Mimir for long-term metrics
  - name: Mimir
    type: prometheus
    access: proxy
    url: http://mimir:9009/prometheus
    editable: false
    jsonData:
      timeInterval: 30s

  # Alertmanager
  - name: Alertmanager
    type: alertmanager
    access: proxy
    url: http://alertmanager:9093
    editable: false
    jsonData:
      implementation: prometheus

  # PostgreSQL (existing database)
  - name: PostgreSQL
    type: postgres
    access: proxy
    url: postgres:5432
    database: ${DB_NAME}
    user: ${DB_USER}
    secureJsonData:
      password: ${DB_PASSWORD}
    jsonData:
      sslmode: disable
      postgresVersion: 1400
```

### 4.3 FastAPI Grafana Proxy

**File:** `app/routers/grafana_proxy.py` (NEW - to be created)

```python
"""
Grafana Proxy Router

Proxies requests to Grafana with SSO authentication.
"""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
import httpx
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/grafana",
    tags=["grafana"]
)

GRAFANA_URL = "http://grafana:3000"


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def grafana_proxy(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Proxy all Grafana requests with SSO authentication.
    Passes X-WEBAUTH-USER header for automatic login.
    """
    # Build target URL
    url = f"{GRAFANA_URL}/{path}"

    # Copy query parameters
    if request.url.query:
        url += f"?{request.url.query}"

    # Prepare headers
    headers = dict(request.headers)
    headers["X-WEBAUTH-USER"] = current_user.username
    headers["Host"] = "grafana:3000"

    # Remove headers that shouldn't be forwarded
    headers.pop("host", None)
    headers.pop("cookie", None)

    # Proxy the request
    async with httpx.AsyncClient() as client:
        # Get request body if present
        body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None

        response = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=30.0
        )

        # Return proxied response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
```

### 4.4 UI Templates

**File:** `templates/grafana_logs.html` (NEW - to be created)

```html
{% extends "layout.html" %}

{% block title %}Logs - Loki{% endblock %}

{% block content %}
<div class="grafana-container">
    <iframe
        id="grafana-iframe"
        src="/grafana/explore?orgId=1&left=%7B%22datasource%22:%22Loki%22,%22queries%22:%5B%7B%22refId%22:%22A%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D"
        frameborder="0"
        width="100%"
        height="100%"
        style="border: none; display: block;">
    </iframe>
</div>

<style>
.grafana-container {
    position: fixed;
    top: 60px; /* Account for navbar */
    left: 250px; /* Account for sidebar */
    right: 0;
    bottom: 0;
    overflow: hidden;
}

/* Responsive: collapse sidebar on mobile */
@media (max-width: 768px) {
    .grafana-container {
        left: 0;
    }
}
</style>
{% endblock %}
```

**File:** `templates/grafana_traces.html` (NEW - to be created)

```html
{% extends "layout.html" %}

{% block title %}Traces - Tempo{% endblock %}

{% block content %}
<div class="grafana-container">
    <iframe
        id="grafana-iframe"
        src="/grafana/explore?orgId=1&left=%7B%22datasource%22:%22Tempo%22,%22queries%22:%5B%7B%22refId%22:%22A%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D"
        frameborder="0"
        width="100%"
        height="100%"
        style="border: none; display: block;">
    </iframe>
</div>

<style>
.grafana-container {
    position: fixed;
    top: 60px;
    left: 250px;
    right: 0;
    bottom: 0;
    overflow: hidden;
}

@media (max-width: 768px) {
    .grafana-container {
        left: 0;
    }
}
</style>
{% endblock %}
```

---

## 5. Implementation Phases

### Phase 1: Grafana Deployment (Week 1, 8 hours)

**Objective:** Deploy Grafana and LGTM stack

**Tasks:**
1. Add services to `docker-compose.yml`:
   - Grafana with SSO config
   - Loki (log aggregation)
   - Tempo (tracing)
   - Mimir (long-term metrics)
   - Alertmanager (alert management)

2. Create provisioning configs:
   - `grafana/provisioning/datasources/datasources.yml`
   - `tempo/tempo.yaml`
   - `mimir/mimir.yaml`
   - `alertmanager/config.yml`

3. Deploy stack:
   ```bash
   docker-compose up -d grafana loki tempo mimir alertmanager
   ```

4. Verify services:
   - Grafana accessible at http://localhost:3000
   - Loki at http://localhost:3100
   - Tempo at http://localhost:3200
   - Mimir at http://localhost:9009

**Deliverables:**
- ✅ All services running
- ✅ Datasources auto-provisioned in Grafana
- ✅ Health checks passing

---

### Phase 2: SSO Integration (Week 1-2, 12 hours)

**Objective:** Enable seamless authentication between AIOps and Grafana

**Tasks:**
1. Create Grafana proxy router (`app/routers/grafana_proxy.py`)
2. Implement `X-WEBAUTH-USER` header passing
3. Configure Grafana auth proxy mode
4. Test user auto-provisioning
5. Verify session management

**Testing:**
```python
# Test SSO flow
1. Login to AIOps as user "alice"
2. Navigate to /grafana/
3. Verify Grafana shows "alice" is logged in
4. Check Grafana user was auto-created
5. Logout from AIOps
6. Verify Grafana session also ends
```

**Deliverables:**
- ✅ SSO working end-to-end
- ✅ No separate Grafana login required
- ✅ Users auto-provisioned on first access

---

### Phase 3: UI Integration (Week 2, 16 hours)

**Objective:** Embed Grafana seamlessly into AIOps UI

**Tasks:**
1. Update sidebar navigation in `templates/layout.html`:
   ```html
   <!-- Add new menu items -->
   <li><a href="/logs">📋 Logs</a></li>
   <li><a href="/traces">🔍 Traces</a></li>
   <li><a href="/alerts">🔔 Alerts</a></li>
   <li><a href="/grafana-dashboards">⚙️ Advanced</a></li>
   ```

2. Create iframe templates:
   - `templates/grafana_logs.html` (Loki Explore)
   - `templates/grafana_traces.html` (Tempo Explore)
   - `templates/grafana_alerts.html` (Alertmanager)
   - `templates/grafana_advanced.html` (Grafana Dashboards)

3. Add routes to `app/main.py`:
   ```python
   @app.get("/logs")
   async def logs_page(request: Request, user: User = Depends(get_current_user)):
       return templates.TemplateResponse("grafana_logs.html", {"request": request, "user": user})
   ```

4. Theme matching:
   - Configure Grafana theme to match AIOps
   - Test dark/light mode consistency
   - Adjust iframe CSS for seamless integration

5. Responsive design:
   - Test on desktop, tablet, mobile
   - Ensure iframe resizes correctly
   - Handle sidebar collapse/expand

**Deliverables:**
- ✅ All Grafana features accessible via AIOps navigation
- ✅ Consistent theme across custom and Grafana pages
- ✅ Responsive design working

---

### Phase 4: Feature Decision Implementation (Week 2, 4 hours)

**Objective:** Document and configure which features use custom vs Grafana

**Tasks:**
1. Create feature routing logic:
   ```
   /dashboards          → Custom builder (keep existing)
   /dashboards/create   → Custom builder (keep existing)
   /playlists           → Custom playlists (keep existing)
   /snapshots           → Custom snapshots (keep existing)
   /logs                → Grafana Loki (new iframe)
   /traces              → Grafana Tempo (new iframe)
   /grafana-dashboards  → Grafana (new iframe)
   ```

2. Update documentation
3. Add tooltips/help text to guide users

**Deliverables:**
- ✅ Clear feature boundaries
- ✅ User documentation updated

---

### Phase 5: Data Flow & Sync (Week 3, 4 hours)

**Objective:** Handle data consistency between systems

**Strategy: MINIMAL SYNC**
- **Keep databases separate** - No complex synchronization
- **Grafana manages:** Grafana-created dashboards, users, settings
- **AIOps manages:** Custom dashboards, permissions, playlists, snapshots
- **Bridge:** Use Grafana API to list Grafana dashboards in AIOps (read-only)

**Tasks:**
1. Create read-only dashboard list endpoint:
   ```python
   @router.get("/grafana-dashboards/list")
   async def list_grafana_dashboards(user: User = Depends(get_current_user)):
       # Call Grafana API to get dashboard list
       # Display in AIOps UI for discovery
   ```

2. Add "Open in Grafana" links to custom dashboards (optional)
3. Document data ownership boundaries

**Deliverables:**
- ✅ No complex data sync required
- ✅ Clear ownership model
- ✅ Optional cross-linking

---

### Phase 6: Testing & Deployment (Week 3-4, TBD)

**Objective:** Validate and deploy to production

**Tasks:**
1. Integration testing:
   - SSO flow
   - All iframe pages load correctly
   - No CORS issues
   - Performance testing (iframe overhead)

2. User acceptance testing:
   - Test with real users
   - Gather feedback on transparency
   - Measure user confusion (should be zero)

3. Documentation:
   - User guide for new features
   - Admin guide for Grafana configuration
   - Troubleshooting guide

4. Deployment:
   - Deploy to staging
   - Smoke tests
   - Deploy to production
   - Monitor for issues

**Deliverables:**
- ✅ Production-ready deployment
- ✅ User documentation
- ✅ Admin documentation

---

## 6. Deployment Strategy

### Development Environment
```bash
# Start all services
docker-compose up -d

# Services:
# - FastAPI: http://localhost:8000
# - Grafana: http://localhost:3000 (proxied via FastAPI)
# - Prometheus: http://localhost:9090
# - Loki: http://localhost:3100
# - Tempo: http://localhost:3200
# - Mimir: http://localhost:9009
# - Alertmanager: http://localhost:9093
```

### Production Deployment

**Requirements:**
- Kubernetes cluster OR Docker Swarm
- Persistent volumes for Grafana, Loki, Tempo, Mimir data
- Load balancer for high availability
- Backup strategy for Grafana dashboards

**Environment Variables:**
```bash
# Grafana
GRAFANA_ADMIN_PASSWORD=<strong-password>
GF_SECURITY_SECRET_KEY=<random-secret>

# Database
DB_NAME=aiops
DB_USER=aiops_user
DB_PASSWORD=<db-password>

# AIOps
JWT_SECRET_KEY=<jwt-secret>
```

---

## 7. Testing & Validation

### Test Cases

| Test Case | Expected Result | Priority |
|-----------|----------------|----------|
| **SSO-001:** User logs into AIOps, navigates to /logs | Grafana Loki appears, user is logged in automatically | P0 |
| **SSO-002:** User logs out of AIOps | Grafana session also ends | P0 |
| **UI-001:** Navigate from Dashboards → Logs → Traces → Dashboards | Seamless transitions, no visual glitches | P0 |
| **UI-002:** Resize browser window | iframe resizes correctly, no scrollbars | P1 |
| **UI-003:** Mobile view | Sidebar collapses, iframe takes full width | P1 |
| **PERF-001:** Load /logs page | Page loads in <2 seconds | P1 |
| **PERF-002:** Query Loki logs | Results appear in <3 seconds | P2 |
| **DATA-001:** Create dashboard in Grafana | Dashboard persists after restart | P0 |
| **DATA-002:** Create custom dashboard in AIOps | Dashboard not visible in Grafana (separate databases) | P1 |
| **PERM-001:** Viewer role user accesses /logs | Can view logs, cannot create dashboards | P2 |

### Performance Benchmarks

**Target Metrics:**
- **SSO login:** <500ms
- **Page load (iframe):** <2s
- **Query execution:** <3s (Loki), <1s (Tempo), <2s (Prometheus)
- **Dashboard rendering:** <1s

---

## 8. Success Metrics

### Technical Metrics
- ✅ Zero SSO failures (100% auto-login success)
- ✅ <2s iframe page load time
- ✅ Zero CORS errors
- ✅ 99.9% uptime for Grafana services

### User Experience Metrics
- ✅ Zero user reports of "separate login required"
- ✅ <5% users notice iframe (transparent experience)
- ✅ User satisfaction score: >4.5/5
- ✅ Feature adoption: >70% users use Logs/Traces within first month

### Business Metrics
- ✅ 196 hours development time saved
- ✅ $19,600-$39,200 cost saved
- ✅ Faster time-to-market for log/trace features
- ✅ Access to 80+ Grafana datasources (future expansion)

---

## Appendix A: API Reference

### Grafana API Endpoints (Proxied)

All Grafana APIs accessible via AIOps proxy:

```
GET  /grafana/api/dashboards/home
GET  /grafana/api/search
POST /grafana/api/dashboards/db
GET  /grafana/api/datasources
GET  /grafana/api/org/users
```

### New AIOps Endpoints

```python
# Grafana proxy
@app.api_route("/grafana/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])

# UI routes
@app.get("/logs")              # Loki Explore
@app.get("/traces")            # Tempo Explore
@app.get("/alerts")            # Alertmanager
@app.get("/grafana-dashboards") # Grafana Dashboards
@app.get("/grafana-dashboards/list")  # List Grafana dashboards (API)
```

---

## Appendix B: Grafana Configuration Reference

### Complete Grafana Environment Variables

```yaml
environment:
  # === SSO AUTHENTICATION ===
  - GF_AUTH_PROXY_ENABLED=true
  - GF_AUTH_PROXY_HEADER_NAME=X-WEBAUTH-USER
  - GF_AUTH_PROXY_HEADER_PROPERTY=username
  - GF_AUTH_PROXY_AUTO_SIGN_UP=true
  - GF_AUTH_PROXY_ENABLE_LOGIN_TOKEN=false

  # === SERVER ===
  - GF_SERVER_ROOT_URL=http://localhost:8000/grafana
  - GF_SERVER_SERVE_FROM_SUB_PATH=true
  - GF_SERVER_DOMAIN=localhost
  - GF_SERVER_ENFORCE_DOMAIN=false

  # === SECURITY ===
  - GF_SECURITY_ADMIN_USER=admin
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
  - GF_SECURITY_SECRET_KEY=${GF_SECRET_KEY}
  - GF_SECURITY_ALLOW_EMBEDDING=true
  - GF_SECURITY_COOKIE_SAMESITE=lax
  - GF_SECURITY_COOKIE_SECURE=false  # true in production with HTTPS

  # === AUTH ===
  - GF_AUTH_DISABLE_LOGIN_FORM=true
  - GF_AUTH_DISABLE_SIGNOUT_MENU=true
  - GF_AUTH_ANONYMOUS_ENABLED=false

  # === THEME ===
  - GF_DEFAULT_THEME=dark
  - GF_UI_DEFAULT_TIMEZONE=browser

  # === USERS ===
  - GF_USERS_ALLOW_SIGN_UP=false
  - GF_USERS_AUTO_ASSIGN_ORG=true
  - GF_USERS_AUTO_ASSIGN_ORG_ROLE=Viewer

  # === LOGGING ===
  - GF_LOG_LEVEL=info
  - GF_LOG_MODE=console
```

---

## Appendix C: Troubleshooting

### Common Issues

**Issue:** Grafana shows "Login required" despite SSO
- **Cause:** `X-WEBAUTH-USER` header not passed
- **Fix:** Check Grafana proxy implementation, verify header in request
- **Debug:** `docker logs aiops-grafana | grep "Auth Proxy"`

**Issue:** iframe shows "X-Frame-Options: DENY"
- **Cause:** `GF_SECURITY_ALLOW_EMBEDDING` not enabled
- **Fix:** Add to Grafana environment variables
- **Restart:** `docker-compose restart grafana`

**Issue:** Grafana shows 404 for `/grafana/` URLs
- **Cause:** `GF_SERVER_SERVE_FROM_SUB_PATH` not enabled
- **Fix:** Enable in environment variables
- **Alternative:** Use path rewriting in proxy

**Issue:** User not auto-created in Grafana
- **Cause:** `GF_AUTH_PROXY_AUTO_SIGN_UP=false`
- **Fix:** Set to `true` in environment variables

**Issue:** Slow iframe loading
- **Cause:** Network latency between containers
- **Fix:** Ensure all services on same Docker network
- **Optimize:** Use `network_mode: host` (development only)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-01 | Claude | Initial planning document |

---

## Next Steps

1. **Review & Approval:** Review this plan with stakeholders
2. **Branch Creation:** ✅ DONE - `claude/grafana-integration-dKuiI` created
3. **Phase 1 Start:** Deploy Grafana and LGTM stack
4. **Iterative Implementation:** Follow phases 1-6
5. **User Testing:** Gather feedback on transparent UX
6. **Production Deployment:** Roll out to production

---

**END OF DOCUMENT**
