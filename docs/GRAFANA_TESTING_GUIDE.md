# Grafana Integration Testing Guide

## 🐛 Issue Fixed

**Problem:** Grafana was breaking out of the iframe and displaying the full Grafana page instead of being embedded within the AIOps interface.

**Root Cause:** Grafana was sending `X-Frame-Options` and `Content-Security-Policy` headers that prevented iframe embedding.

**Solution:**
1. Proxy strips frame-busting headers from Grafana responses
2. Template routes add CSP headers to allow iframe embedding

---

## 🔄 How to Apply the Fix

### Step 1: Restart the Application

```bash
# Stop the containers
docker-compose down

# Rebuild and start (to pick up code changes)
docker-compose up -d --build remediation-engine

# Or just restart if image is up to date
docker-compose restart remediation-engine
```

### Step 2: Check Services Are Running

```bash
# Verify all services are healthy
docker-compose ps

# Check logs for errors
docker logs aiops-grafana
docker logs remediation-engine
```

---

## ✅ Testing the Fix

### Test 1: Grafana Advanced Page

1. **Navigate to:** `http://localhost:8080/grafana-advanced`

2. **Expected Result:**
   ```
   ┌─────────────────┬──────────────────────────────────┐
   │                 │                                  │
   │  AIOps Sidebar  │    Grafana Content (iframe)     │
   │                 │                                  │
   │  - Dashboard    │    Welcome to Grafana            │
   │  - Observability│    [Grafana Dashboard List]      │
   │    • Logs       │                                  │
   │    • Traces     │                                  │
   │    • Alerts     │                                  │
   │  - AI           │                                  │
   │  - Rules        │                                  │
   │                 │                                  │
   └─────────────────┴──────────────────────────────────┘
   ```

3. **❌ WRONG (Before Fix):**
   - Full Grafana page, NO AIOps sidebar
   - URL might change to `/grafana/`

4. **✅ CORRECT (After Fix):**
   - AIOps sidebar visible on left
   - Grafana content in iframe on right
   - URL stays at `/grafana-advanced`

### Test 2: Logs Page (Loki)

1. **Navigate to:** `http://localhost:8080/logs`
2. **Expected:** AIOps sidebar + Loki Explore iframe
3. **Check:** Can see log query interface

### Test 3: Traces Page (Tempo)

1. **Navigate to:** `http://localhost:8080/traces`
2. **Expected:** AIOps sidebar + Tempo Explore iframe
3. **Check:** Can see trace search interface

### Test 4: Alert Manager Page

1. **Navigate to:** `http://localhost:8080/grafana-alerts`
2. **Expected:** AIOps sidebar + Alertmanager iframe
3. **Check:** Can see alerts list

---

## 🔍 Debugging

### Check 1: Inspect Network Requests

Open browser DevTools (F12) → Network tab:

1. Navigate to `/grafana-advanced`
2. Look for the initial page request
3. **Check response headers:**
   - ✅ Should have: `X-Frame-Options: SAMEORIGIN`
   - ✅ Should have: `Content-Security-Policy: frame-src 'self' ...`

4. Look for iframe requests to `/grafana/`
5. **Check those response headers:**
   - ❌ Should NOT have: `X-Frame-Options`
   - ❌ Should NOT have: `Content-Security-Policy`

### Check 2: Console Errors

Open browser DevTools → Console tab:

**❌ Bad (iframe blocked):**
```
Refused to display 'http://localhost:8080/grafana/' in a frame because it set 'X-Frame-Options' to 'deny'.
```

**✅ Good (no errors):**
```
(No frame-related errors)
```

### Check 3: Inspect Element

1. Right-click on Grafana content
2. Select "Inspect"
3. Look for:
   ```html
   <div class="grafana-container">
     <iframe id="grafana-iframe" src="/grafana/?orgId=1">
       <!-- Grafana content should be here -->
     </iframe>
   </div>
   ```

---

## 🚨 Common Issues

### Issue 1: Still Seeing Full Grafana Page

**Symptom:** Navigate to `/grafana-advanced` but only see Grafana, no AIOps sidebar

**Possible Causes:**
1. **Code not reloaded** - Restart didn't pick up changes
2. **Browser cache** - Old page cached
3. **JavaScript redirect** - Grafana might have JS frame-busting

**Solutions:**
```bash
# 1. Force rebuild
docker-compose down
docker-compose build --no-cache remediation-engine
docker-compose up -d

# 2. Hard refresh browser
# Chrome/Firefox: Ctrl + Shift + R (or Cmd + Shift + R on Mac)
# Clear browser cache

# 3. Check for JS errors in console
# Open DevTools → Console → look for errors
```

### Issue 2: Blank Page or "Loading..."

**Symptom:** See AIOps sidebar but iframe is blank or stuck on "Loading Grafana Dashboards..."

**Possible Causes:**
1. Grafana service not running
2. Proxy not working
3. CORS issues

**Solutions:**
```bash
# Check Grafana is running
docker logs aiops-grafana

# Should see:
# "HTTP Server Listen" or "Server is operational"

# Test direct Grafana access
curl http://localhost:3000/api/health

# Test proxy
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/grafana/api/health
```

### Issue 3: "401 Unauthorized" or Login Loop

**Symptom:** Grafana keeps redirecting to login or shows 401 errors

**Possible Causes:**
1. SSO not configured correctly
2. X-WEBAUTH-USER header not being sent
3. User not provisioned in Grafana

**Solutions:**
1. Check Grafana logs for SSO errors:
   ```bash
   docker logs aiops-grafana | grep -i "auth proxy"
   ```

2. Verify environment variables:
   ```bash
   docker exec aiops-grafana env | grep GF_AUTH
   ```

3. Test SSO header:
   ```bash
   # Login to AIOps, get JWT token, then:
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://localhost:8080/grafana/api/user

   # Should return user info without login redirect
   ```

---

## 📊 Success Criteria

After applying the fix, you should be able to:

- ✅ Navigate to `/grafana-advanced` and see both AIOps sidebar + Grafana iframe
- ✅ Navigate to `/logs` and see Loki Explore embedded
- ✅ Navigate to `/traces` and see Tempo Search embedded
- ✅ Navigate to `/grafana-alerts` and see Alertmanager embedded
- ✅ Click between pages without any redirects or full-page loads
- ✅ No console errors about X-Frame-Options
- ✅ Single login (no separate Grafana login required)

---

## 🔧 Advanced Debugging

### Enable Verbose Logging

Add to `docker-compose.yml` under Grafana environment:
```yaml
- GF_LOG_LEVEL=debug
- GF_LOG_MODE=console
```

Restart Grafana:
```bash
docker-compose restart grafana
docker logs -f aiops-grafana
```

### Test SSO Flow Manually

1. **Get JWT token from browser:**
   - Login to AIOps
   - Open DevTools → Application → Cookies
   - Find `access_token` or `jwt_token`

2. **Test proxy with token:**
   ```bash
   TOKEN="your-jwt-token-here"

   # Test Grafana health via proxy
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8080/grafana/api/health

   # Test SSO user provisioning
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8080/grafana/api/user
   ```

3. **Expected response:**
   ```json
   {
     "id": 1,
     "login": "your-username",
     "email": "",
     "name": "your-username",
     "orgId": 1,
     "isGrafanaAdmin": false
   }
   ```

---

## 📝 Next Steps After Testing

Once the fix is working:

1. **Test all 4 pages** (Logs, Traces, Alerts, Advanced)
2. **Verify SSO** - no separate Grafana login
3. **Check theme consistency** - dark mode matches
4. **Test navigation** - sidebar links work
5. **Monitor performance** - iframe loads quickly

If everything works:
- ✅ Mark as tested
- ✅ Document any issues found
- ✅ Ready for production deployment

---

## 🆘 Still Not Working?

If the fix doesn't work after following this guide:

1. **Capture evidence:**
   - Screenshot of the issue
   - Browser console errors
   - Network tab showing requests/responses
   - Docker logs (`docker logs aiops-grafana` and `docker logs remediation-engine`)

2. **Check browser compatibility:**
   - Test in different browser (Chrome, Firefox, Safari)
   - Try incognito/private mode

3. **Verify configuration:**
   ```bash
   # Check Grafana config
   docker exec aiops-grafana grafana-cli admin settings

   # Check proxy is registered
   docker exec remediation-engine grep -r "grafana_proxy" app/
   ```

4. **Contact support** with evidence collected above

---

**Last Updated:** 2025-01-24
**Version:** 1.0
**Related Commit:** `cbc81ba` - "fix: Strip frame-busting headers and add CSP for iframe embedding"
