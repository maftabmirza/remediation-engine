# Dashboard Builder Testing Guide

Complete testing guide for the Prometheus Dashboard Builder feature.

## Prerequisites

1. **Running Application**: Ensure the application is running
2. **Prometheus Server**: Have a Prometheus server accessible (can use the default from docker-compose)
3. **Authentication**: Be logged in as a user with appropriate permissions

## Testing Checklist

### ✅ 1. Datasource Management

#### Create Datasource
- [ ] Navigate to `/datasources`
- [ ] Click "Add Datasource"
- [ ] Fill in the form:
  - Name: `Test Prometheus`
  - URL: `http://prometheus:9090` (or your Prometheus URL)
  - Description: `Test datasource for validation`
  - Authentication: None
  - Timeout: 30
  - Set as Default: ✓
  - Enabled: ✓
- [ ] Click "Save"
- [ ] Verify datasource appears in the table
- [ ] Verify "DEFAULT" badge is displayed

#### Test Connection
- [ ] Click the lightning bolt icon (Test Connection) on the datasource
- [ ] Verify success message shows version info
- [ ] Try with invalid URL and verify error message

#### Edit Datasource
- [ ] Click edit icon on a datasource
- [ ] Change description
- [ ] Save and verify changes persist

#### Delete Datasource
- [ ] Create a non-default datasource
- [ ] Delete it and verify it's removed
- [ ] Try to delete default datasource (should fail with error)

### ✅ 2. Panel Creation

#### Access Panel Templates
- [ ] Navigate to `/panels`
- [ ] Verify 15 pre-built templates are displayed
- [ ] Check that templates have "TEMPLATE" badge
- [ ] Filter by "Templates Only" checkbox

#### Create Panel from Template
- [ ] Click "Create Panel"
- [ ] Select "Query Examples" dropdown
- [ ] Choose "CPU Usage (%)"
- [ ] Verify query is populated
- [ ] Fill in:
  - Name: `My CPU Panel`
  - Datasource: Select your datasource
  - Panel Type: Graph
  - Time Range: 1h
- [ ] Click "Test Query" button
- [ ] Verify query validation (should show success or error)
- [ ] Save panel
- [ ] Verify it appears in the grid

#### Create Custom Panel
- [ ] Click "Create Panel"
- [ ] Manually enter:
  - Name: `Custom Query Panel`
  - Description: `Testing custom PromQL`
  - Datasource: Your datasource
  - Query: `up` (simple query)
  - Legend: `{{instance}}`
  - Panel Type: Gauge
  - Tags: `monitoring, test`
- [ ] Test query
- [ ] Save panel
- [ ] Verify it's created

#### Test Query Validation
- [ ] Create a panel with invalid PromQL: `invalid{}`
- [ ] Click "Test Query"
- [ ] Verify error message is shown
- [ ] Correct the query
- [ ] Re-test and verify success

#### Filter Panels
- [ ] Use search box to filter by name
- [ ] Filter by datasource
- [ ] Filter by type (graph, gauge, stat, table)
- [ ] Filter templates only

#### Edit Panel
- [ ] Click edit icon on a panel
- [ ] Modify query
- [ ] Save changes
- [ ] Verify changes persist

#### Delete Panel
- [ ] Create a test panel
- [ ] Delete it
- [ ] Confirm deletion works

### ✅ 3. Dashboard Builder

#### Create Dashboard
- [ ] Navigate to `/dashboards-builder`
- [ ] Click "New Dashboard"
- [ ] Fill in:
  - Name: `Infrastructure Monitoring`
  - Description: `CPU, Memory, and Disk metrics`
  - Time Range: 24h
  - Refresh Interval: 60s
  - Auto Refresh: ✓
  - Set as Home: ✓
- [ ] Save dashboard
- [ ] Verify it appears with "HOME" badge

#### Add Panels to Dashboard
- [ ] Click "Add Panels" on your dashboard
- [ ] Select 3-5 panels from the list
- [ ] Click checkboxes to select them
- [ ] Click "Add Selected"
- [ ] Verify success message
- [ ] Verify panel count updates

#### View Dashboard
- [ ] Click the eye icon to view dashboard
- [ ] Verify `/dashboard-view/{id}` page loads
- [ ] Verify panels are displayed
- [ ] Verify charts render with data (if Prometheus has data)
- [ ] Test time range selector
- [ ] Test auto-refresh toggle

#### Dashboard Features
- [ ] Create multiple dashboards
- [ ] Test favorites (checkbox)
- [ ] Filter favorites only
- [ ] Search dashboards
- [ ] Edit dashboard metadata
- [ ] Delete dashboard

### ✅ 4. API Testing (cURL Examples)

#### Test Datasources API
```bash
# List datasources
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/datasources/

# Create datasource
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Prom",
    "url": "http://prometheus:9090",
    "auth_type": "none",
    "is_default": false,
    "is_enabled": true
  }' \
  http://localhost:8080/api/datasources/

# Test connection
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/datasources/{datasource_id}/test
```

#### Test Panels API
```bash
# List panels
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/panels/?limit=100

# Create panel
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CPU Usage",
    "datasource_id": "YOUR_DATASOURCE_ID",
    "promql_query": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
    "panel_type": "graph",
    "time_range": "1h"
  }' \
  http://localhost:8080/api/panels/

# Test query
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "datasource_id": "YOUR_DATASOURCE_ID",
    "promql_query": "up"
  }' \
  http://localhost:8080/api/panels/test-query

# Get panel data
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/panels/{panel_id}/data
```

#### Test Dashboards API
```bash
# List dashboards
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/dashboards/

# Create dashboard
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Dashboard",
    "time_range": "24h",
    "refresh_interval": 60,
    "auto_refresh": true
  }' \
  http://localhost:8080/api/dashboards/

# Add panel to dashboard
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "panel_id": "YOUR_PANEL_ID",
    "grid_x": 0,
    "grid_y": 0,
    "grid_width": 12,
    "grid_height": 4
  }' \
  http://localhost:8080/api/dashboards/{dashboard_id}/panels

# Get dashboard details
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/dashboards/{dashboard_id}
```

### ✅ 5. Database Migration Testing

```bash
# Check migration status
# (If alembic is available)
python -m alembic current

# Apply migrations
python -m alembic upgrade head

# Verify tables exist
psql -U aiops -d aiops -c "\dt" | grep prometheus
```

Expected tables:
- `prometheus_datasources`
- `prometheus_panels`
- `dashboards`
- `dashboard_panels`

### ✅ 6. Error Handling

#### Test Error Cases
- [ ] Create panel without selecting datasource
- [ ] Create panel with empty query
- [ ] Test query with malformed PromQL
- [ ] Try to delete default datasource
- [ ] Add non-existent panel to dashboard
- [ ] Create datasource with duplicate name
- [ ] Create datasource with invalid URL format
- [ ] Test connection to unreachable Prometheus server

### ✅ 7. UI/UX Testing

#### Responsive Design
- [ ] Test on desktop (1920x1080)
- [ ] Test on tablet (768px)
- [ ] Test on mobile (375px)
- [ ] Verify modals are scrollable
- [ ] Verify tables are responsive

#### User Experience
- [ ] Verify all toasts/notifications appear
- [ ] Check loading states
- [ ] Verify confirmation dialogs
- [ ] Test form validation messages
- [ ] Check empty states (no datasources, no panels, no dashboards)

### ✅ 8. Integration Testing

#### Full Workflow
1. [ ] Create datasource
2. [ ] Test connection
3. [ ] Create 5 panels (mix of templates and custom)
4. [ ] Test each panel query
5. [ ] Create dashboard
6. [ ] Add all panels to dashboard
7. [ ] View dashboard
8. [ ] Verify all charts render
9. [ ] Edit a panel from dashboard view
10. [ ] Remove a panel from dashboard
11. [ ] Clone dashboard
12. [ ] Set as favorite
13. [ ] Delete non-default items

### ✅ 9. Performance Testing

- [ ] Create 50+ panels and verify UI performance
- [ ] Add 20+ panels to a dashboard
- [ ] Test dashboard with auto-refresh on
- [ ] Verify no memory leaks (check browser DevTools)
- [ ] Test concurrent API requests

### ✅ 10. Security Testing

- [ ] Verify authentication required for all endpoints
- [ ] Test with expired token
- [ ] Test with invalid token
- [ ] Verify passwords are encrypted in database
- [ ] Test SQL injection in search fields
- [ ] Test XSS in panel names/descriptions

## Common Issues and Solutions

### Issue: "Prometheus connection failed"
**Solution**: Verify Prometheus URL is correct and server is running

### Issue: "No panel templates appearing"
**Solution**: Check application logs for template seeding errors. Default datasource must exist first.

### Issue: "Charts not rendering on dashboard view"
**Solution**:
- Verify Prometheus has data for the queries
- Check browser console for errors
- Verify panel queries return data

### Issue: "Migration failed"
**Solution**:
- Check migration chain in alembic/versions
- Verify down_revision matches previous migration
- Check database for existing tables

### Issue: "Encryption key error"
**Solution**: Set ENCRYPTION_KEY environment variable with a Fernet key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Test Data Cleanup

After testing, clean up test data:

```sql
-- Delete test dashboards
DELETE FROM dashboards WHERE name LIKE '%Test%';

-- Delete test panels (non-templates)
DELETE FROM prometheus_panels WHERE is_template = false AND name LIKE '%Test%';

-- Delete test datasources (non-default)
DELETE FROM prometheus_datasources WHERE is_default = false AND name LIKE '%Test%';
```

## Automated Testing (Future Enhancement)

Consider adding:
- Pytest tests for API endpoints
- Selenium tests for UI workflows
- Load testing with locust
- CI/CD integration

## Sign-Off Checklist

All tests complete:
- [ ] Datasource CRUD works
- [ ] Panel CRUD works
- [ ] Dashboard CRUD works
- [ ] Query testing works
- [ ] Connection testing works
- [ ] Templates seed correctly
- [ ] Dashboard view renders charts
- [ ] All error cases handled
- [ ] UI is responsive
- [ ] No console errors
- [ ] APIs return correct status codes
- [ ] Authentication enforced

**Tested By**: ___________
**Date**: ___________
**Version**: 2.0.0
**Status**: ☐ Pass  ☐ Fail
