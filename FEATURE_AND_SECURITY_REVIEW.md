# Remediation Engine - Feature Comparison & Security Deep Dive

**Review Date:** 2026-02-13
**Branch:** `claude/review-branch-maturity-RxmAm`
**Scope:** Feature-by-feature comparison with commercial AIOps platforms + exhaustive security audit with code-level findings

---

# PART 1: FEATURE COMPARISON

## Feature Maturity Matrix

| Feature | Maturity | Rating | vs. PagerDuty | vs. Datadog | vs. BigPanda | vs. Moogsoft |
|---------|----------|--------|---------------|-------------|--------------|--------------|
| Alert Ingestion | Intermediate | 6/10 | Behind (700+ integrations) | Behind (600+ integrations) | Behind (300+ tools) | Comparable |
| AI/ML Capabilities | **Advanced** | **9/10** | **Ahead** (multi-LLM, MCP) | **Ahead** (multi-provider) | **Ahead** (agentic) | **Ahead** |
| Alert Clustering | Intermediate | 6/10 | Ahead (3-layer) | Behind (Watchdog) | Behind (Open Box ML) | Behind (72 patents) |
| Remediation Execution | **Advanced** | **9/10** | **Ahead** (SSH/WinRM) | **Ahead** (direct exec) | **Ahead** (direct exec) | **Ahead** |
| Knowledge Base (RAG) | Intermediate | 7/10 | **Ahead** (none native) | **Ahead** (none native) | **Ahead** (none native) | **Ahead** |
| Observability | Intermediate | 6/10 | Comparable | Behind (unified) | Comparable | Comparable |
| ITSM Integration | Intermediate | 5/10 | Behind (700+) | Behind (CI/CD native) | Behind (deep SNOW) | Comparable |
| Incident Management | Basic | 4/10 | Behind (flagship) | Comparable | Behind | Comparable |
| RBAC / Multi-Tenancy | Basic | 4/10 | Behind (teams) | Behind (teams, SSO) | Behind | Comparable |
| On-Call & Scheduling | **Not Implemented** | 0/10 | Behind (flagship) | N/A | N/A | N/A |
| Analytics & Reporting | Intermediate | 6/10 | Comparable | Behind (SLO mgmt) | Comparable | Ahead |
| Topology & Discovery | Basic | 3/10 | N/A | Behind (service map) | Behind (auto-discover) | Behind |

---

## 1. Alert Ingestion & Processing — INTERMEDIATE (6/10)

### What Exists
- **Prometheus/Alertmanager** native webhook integration with full alert parsing
- Deduplication by fingerprint + timestamp
- PII detection integrated into ingestion pipeline (Presidio scans alert payloads)
- Rules engine with JSON Logic + pattern matching (wildcards, regex)
- Actions: `auto_analyze`, `ignore`, `manual` with background task queue

### What's Missing vs. Commercial Platforms
| Gap | PagerDuty | Datadog | Impact |
|-----|-----------|---------|--------|
| Pre-built connectors | 700+ integrations | 600+ integrations | Limits adoption in heterogeneous environments |
| Datadog/Splunk/Elastic/CloudWatch ingestion | Native | Native | Forces Prometheus-only monitoring |
| Email/SMS alert ingestion | Supported | Supported | No legacy monitoring support |
| SNS/SQS/EventBridge | Supported | Native | No cloud-native event bus |

### Verdict
Solid for Prometheus shops. The PII-aware ingestion pipeline is a differentiator. But single-source dependency (Alertmanager) is a significant limitation for enterprises with diverse monitoring stacks.

---

## 2. AI/ML Capabilities — ADVANCED (9/10) - Industry-Leading for Self-Hosted

### What Exists

**Multi-Provider LLM Support** (via LiteLLM):
| Provider | Models | Native Tool Calling | Status |
|----------|--------|---------------------|--------|
| Anthropic | Claude 3/3.5/4 | Yes | Full support |
| OpenAI | GPT-4, GPT-4o | Yes | Full support |
| Google | Gemini | Yes | Full support |
| Ollama | Llama, Mistral, etc. | No (ReAct fallback) | Full support |

**Agent Framework** (25 agentic service files, 14+ agent types):
1. `NativeToolAgent` - Provider-native function calling (OpenAI/Anthropic/Google)
2. `ReActAgent` - Text-based ReAct pattern for Ollama/local LLMs
3. `AiTroubleshootAgent` - Specialized incident troubleshooting
4. `AiInquiryAgent` - User inquiry handling
5. `AiAlertHelpAgent` - Alert-specific analysis
6. `TroubleshootNativeAgent` - Native function calls for troubleshooting
7. `AgenticOrchestrator` - Routes to appropriate agent based on provider capabilities

**MCP Integration** (7 MCP service files):
- Standard protocol support (`initialize`, `list_tools`, `call_tool`)
- Composite tool registry with 10+ tool categories
- Grafana MCP for AI-driven dashboard/metric queries

**Safety Mechanisms**:
- PII/secrets detection and redaction on LLM responses
- Circuit breaker for rate limiting
- Blackout windows for safety
- AI permission service (checks user permissions before agent execution)

### How This Compares

| Capability | This Engine | PagerDuty | Datadog | BigPanda |
|---|---|---|---|---|
| LLM providers | 4+ (swappable) | 1 (proprietary) | 1 (proprietary) | 1 (proprietary) |
| Agent types | 14+ | 3 | 1 (Bits AI) | 1 |
| Native tool calling | Yes (multi-provider) | Limited | Limited | No |
| MCP support | Yes | No | No | No |
| Local model support | Yes (Ollama) | No | No | No |
| PII redaction in AI | Yes (dual-engine) | Basic | No | No |

### Verdict
**This is the strongest feature area.** Multi-provider LLM abstraction, 14+ specialized agents, MCP standard support, and local model capability are ahead of every commercial AIOps platform. PagerDuty's 3 AI agents and Datadog's Bits AI are locked to their own AI backends. The ability to run Claude, GPT-4, Gemini, or fully local Ollama models in the same framework is a genuine enterprise differentiator for data sovereignty and vendor flexibility.

---

## 3. Alert Clustering & Correlation — INTERMEDIATE (6/10)

### 3-Layer Clustering Strategy

| Layer | Coverage | Algorithm | Complexity |
|---|---|---|---|
| Layer 1: Exact Match | ~70% | Hash of `(alert_name, instance, job)` | O(n) |
| Layer 2: Temporal | ~20% | 5-minute sliding window by alert name | O(n log n) |
| Layer 3: Semantic | ~10% | TF-IDF + cosine similarity (threshold 0.7) | O(n²) |

**Change Correlation**:
- Groups alerts by application ID, instance/host, time window (15 min)
- LLM-based root cause analysis via JSON mode

### Gap Analysis vs. Commercial
| Capability | This Engine | BigPanda | Moogsoft | PagerDuty |
|---|---|---|---|---|
| Adaptive thresholds | No (hardcoded 0.7) | Yes (ML-trained) | Yes (patented) | No |
| Topology-aware correlation | No | Yes | Yes | No |
| Signature learning | No | Yes (Open Box ML) | Yes (72 patents) | No |
| Claimed noise reduction | ~60% (estimated) | 90%+ (case studies) | 80%+ (marketing) | ~50% |

### Verdict
The 3-layer approach (exact + temporal + semantic) is architecturally sound. Semantic clustering with TF-IDF is more sophisticated than PagerDuty's rule-based grouping. However, hardcoded thresholds, no adaptive learning, and no topology awareness put it behind BigPanda and Moogsoft, which have years of ML training and patented algorithms.

---

## 4. Remediation Execution — ADVANCED (9/10) - Industry-Leading

### Execution Engines

**Linux (SSH)** via AsyncSSH:
- Key-based + password authentication
- Sudo elevation (password/passwordless)
- Command streaming with real-time output
- Interactive stdin support
- File transfer (SCP/SFTP)
- Timeout handling, process tracking

**Windows (WinRM)** via pywinrm:
- NTLM/Kerberos authentication
- PowerShell + CMD execution
- Async via executor threads
- SSL/cert validation options

**Runbook Framework**:
- Visual YAML/JSON definition
- Step types: bash, powershell, conditional, loop, manual approval
- Execution modes: `auto`, `semi-auto`, `manual`

**Safety Mechanisms**:
- Circuit breaker (open/half-open/closed states)
- Max executions per hour limits
- Cooldown between targets
- Approval workflows with role-based gates
- Approval timeout
- Blackout windows (prevent execution during maintenance)

### How This Compares

| Capability | This Engine | PagerDuty | BigPanda | Moogsoft |
|---|---|---|---|---|
| Direct SSH execution | Yes (AsyncSSH) | No (webhook only) | No | No |
| Direct WinRM execution | Yes | No | No | No |
| Interactive terminal | Yes (WebSocket) | No | No | No |
| Runbook engine | Full (YAML/JSON) | Workflow builder | Webhook triggers | Basic |
| Circuit breaker | Yes | No | No | No |
| Blackout windows | Yes | Manual | No | No |
| Approval workflows | Yes (role-based) | Yes (basic) | No | No |

### Verdict
**This is the strongest differentiator vs. commercial platforms.** PagerDuty, BigPanda, and Moogsoft all stop at "trigger a webhook" or "open a ticket." This engine provides direct SSH/WinRM command execution with an interactive web terminal, AI-assisted troubleshooting, and a sophisticated runbook framework with circuit breakers and blackout windows. No commercial AIOps platform matches this remediation depth.

---

## 5. Knowledge Base & RAG — INTERMEDIATE (7/10)

### What Exists
- Document upload: Text, Markdown, PDF, Images
- PDF text extraction + image extraction
- **Vision AI** (Claude Vision) analyzes extracted architecture diagrams
- OpenAI embeddings (`text-embedding-3-small`, 1536 dimensions)
- Vector similarity search via pgvector (cosine distance)
- Min similarity threshold: 0.3 (tuned for recall)
- Full-text fallback if embeddings fail
- Application-scoped knowledge filtering (`app_id`)

### Gap vs. Mature RAG Systems
- Embeddings not automatically injected into LLM prompt context
- No chunk-level citations or provenance tracking
- No feedback loop to improve retrieval quality
- No re-ranking (single-pass vector search only)

### Commercial Comparison
No commercial AIOps platform (PagerDuty, Datadog, BigPanda, Moogsoft) has a built-in RAG knowledge base. Vision AI for diagram analysis is unique in the space.

---

## 6. ITSM Integration — INTERMEDIATE (5/10)

### Generic JSON API Connector
- Configurable field mapping via JSONPath
- Auth methods: Bearer token, Basic auth, API key, No auth
- Pagination: Offset-based, Cursor-based, Keyset-based
- Bi-directional sync worker (scheduled)
- Supported platforms (via generic config): ServiceNow, Jira, Azure DevOps, any REST API

### Gap vs. PagerDuty (700+ Integrations)
- No pre-built templates (each ITSM requires manual field mapping)
- Sync is scheduled, not real-time event-driven
- No topology awareness for change impact analysis
- No deep ServiceNow bi-directional sync (PagerDuty/BigPanda have this out-of-box)

---

## 7. Incident Management — BASIC (4/10)

### What Exists
- Status tracking (open/closed), severity levels, priority tiers
- MTTR metrics: avg, p50, p95, p99 by service/severity
- Trend analysis (daily/weekly)
- Regression detection (% degradation vs. baseline)

### Critical Gaps
| Missing Feature | PagerDuty | Impact |
|---|---|---|
| Escalation policies | Core feature | No automatic escalation when incidents aren't acknowledged |
| On-call integration | Core feature | Can't page the right person |
| Post-mortem workflows | Built-in | No formal RCA process |
| War room / collaboration | Built-in | No real-time team coordination |
| SLA enforcement | Built-in | MTTR tracked but not enforced |

---

## 8. On-Call & Scheduling — NOT IMPLEMENTED (0/10)

The `scheduler_service.py` handles **runbook scheduling** (cron/interval execution), not on-call management. There is:
- No on-call rotation management
- No escalation policies
- No notification channels (phone, SMS, Slack, email)
- No override/swap management
- No on-call analytics

This is PagerDuty's flagship feature and the most significant functional gap in the platform.

---

## 9. Topology & Service Discovery — BASIC (3/10)

### What Exists
- `Application` model: name, tech stack, criticality, team owner
- `ApplicationComponent`: hostname, IP, component type (compute, database, cache, queue)
- Manual dependency mapping (many-to-many)
- Alert label matching (infer service from Prometheus `job` label)

### What's Missing
- No auto-discovery from Kubernetes API, cloud provider APIs, or APM traces
- No topology visualization (dependency graph)
- No impact analysis ("if X fails, what breaks?")
- No CMDB integration

---

## Unique Capabilities (Industry-Leading)

These features have **no equivalent** in PagerDuty, Datadog, BigPanda, or Moogsoft:

1. **Multi-Agent AI Framework** — 14+ agent types with provider-agnostic orchestration across 4+ LLM providers
2. **Vision AI for Knowledge** — Extracts knowledge from architecture diagrams via Claude Vision
3. **SSH/WinRM Direct Execution** — Remediate without webhook chains, with interactive web terminal
4. **MCP Standard Compliance** — Future-proof tool integration ahead of the market
5. **Runbook Safety Mechanisms** — Circuit breaker, blackout windows, approval timeouts
6. **3-Layer Alert Clustering** — Exact + temporal + semantic in one pipeline
7. **PII Dual-Engine Detection** — Presidio + detect-secrets with false positive handling in AI prompts

---

---

# PART 2: SECURITY DEEP DIVE

## Risk Summary

| Severity | Count | Categories |
|---|---|---|
| **CRITICAL** | 5 | Unauthenticated endpoints, default credentials, exposed secrets |
| **HIGH** | 8 | Missing access control, injection vectors, unprotected proxies |
| **MEDIUM** | 12 | Cookie security, PII gaps, dependency risks, missing headers |
| **LOW** | 4 | Password truncation, Presidio bugs, CSRF, predictable UIDs |

---

## CRITICAL Findings

### C1. Unauthenticated Webhook Endpoint

**File:** `app/routers/webhook.py` — line 136
```python
@router.post("/alerts")
async def receive_alertmanager_webhook(
    webhook: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
```
**Risk:** `/webhook/alerts` has **NO authentication**. Any attacker can inject arbitrary alerts, trigger `auto_analyze` rules, and potentially execute runbooks through the auto-remediation pipeline without any credentials.
**Impact:** Full alert injection → rule-triggered remediation → unauthorized command execution
**Fix:** Add API key header validation:
```python
@router.post("/alerts")
async def receive_alertmanager_webhook(
    webhook: AlertmanagerWebhook,
    x_api_key: str = Header(...),
    ...
):
    if not hmac.compare_digest(x_api_key, settings.webhook_api_key):
        raise HTTPException(status_code=401)
```

---

### C2. Unauthenticated Grafana Proxy

**File:** `app/routers/grafana_proxy.py` — line 144
```python
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def grafana_proxy(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional)  # <-- OPTIONAL
):
```
**Risk:** Uses `get_current_user_optional` — **unauthenticated users can proxy requests** to Grafana including `PUT`/`DELETE`/`PATCH`. An attacker can modify dashboards, alerts, datasources, and access all metrics without logging in.
**Fix:** Change to `get_current_user` (required).

---

### C3. Default Credentials with No Startup Validation

**File:** `app/config.py` — lines 17, 24-25
```python
jwt_secret: str = "your-secret-key-change-in-production"
admin_username: str = "admin"
admin_password: str = "admin123"
```
**Risk:** If environment variables are not set, the application starts with trivially guessable credentials. There is no validation at startup to reject defaults.
**Fix:** Add startup validation that refuses to start with default values.

---

### C4. Credentials Committed to Git

**File:** `.env.local` — committed to repository
```
POSTGRES_PASSWORD=aiops_secure_password
JWT_SECRET=local-dev-jwt-secret-key-f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4
ENCRYPTION_KEY=cIDGZVsAgjGDEWFScCjQ5IinYKXx2iB8_abv6ImE3Wo=
ADMIN_PASSWORD=Passw0rd
```
**Risk:** All development credentials are in Git history. Even if removed now, they exist in commit history and must be rotated.
**Fix:** Add `.env.local` to `.gitignore`, rotate ALL exposed secrets, use `git filter-branch` or BFG to clean history.

---

### C5. Database Credentials in docker-compose.yml Defaults

**File:** `docker-compose.yml` — lines 32-37
```yaml
- POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-aiops_secure_password}
- DATABASE_URL=postgresql://${POSTGRES_USER:-aiops}:${POSTGRES_PASSWORD:-aiops_secure_password}@postgres:5432/${POSTGRES_DB:-aiops}?sslmode=disable
```
**Risk:** Hardcoded default password + `sslmode=disable`. If deployed without overriding env vars, database is accessible with known credentials over unencrypted connections.

---

## HIGH Findings

### H1. Unprotected Prometheus Configuration Endpoints

**File:** `app/routers/prometheus.py` — lines 63-70
```python
@router.get("/config")
async def get_prometheus_config() -> PrometheusConfig:
```
**Risk:** No `Depends(get_current_user)` — anyone can read AND modify (`PUT /config`) Prometheus configuration without authentication. Exposes internal infrastructure details.

---

### H2. No Account Lockout Mechanism

**File:** `app/routers/auth.py` — lines 40-48
```python
user = authenticate_user(db, login_data.username, login_data.password)
if not user:
    AUTH_ATTEMPTS.labels(status="failed").inc()
    raise HTTPException(status_code=401, detail="Invalid username or password")
```
**Risk:** Rate limit is 5/minute, but no account lockout after N failures. Attacker can make 5 attempts/minute indefinitely = 7,200 attempts/day. With a dictionary attack this is exploitable.
**Fix:** Track failed attempts per account, lock after 5 failures for 15 minutes.

---

### H3. SQL Wildcard Injection (6+ Locations)

**Files and lines:**
| File | Line | Code |
|---|---|---|
| `app/routers/alerts.py` | 48 | `Alert.alert_name.ilike(f"%{alert_name}%")` |
| `app/routers/remediation.py` | 80-81 | `Runbook.name.ilike(f"%{search}%")` |
| `app/routers/incidents.py` | 61, 64, 67, 70 | `IncidentEvent.status.ilike(f"%{status}%")` |
| `app/routers/servers.py` | (search) | `Server.hostname.ilike(f"%{search}%")` |
| `app/routers/application_profiles_api.py` | 99 | `ApplicationProfile.language.ilike(f"%{language}%")` |
| `app/routers/applications.py` | 90-91 | `Application.name.ilike(f"%{search}%")` |

**Risk:** While SQLAlchemy parameterizes the query, `%` and `_` wildcards are not escaped. Attacker input like `%_%_%_%` forces expensive pattern matching (ReDoS-like). Input `%` returns all records (information disclosure).
**Fix:**
```python
def escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

query.filter(Alert.alert_name.ilike(f"%{escape_like(alert_name)}%", escape='\\'))
```

---

### H4. LogQL Injection

**File:** `app/services/query_translator.py` — lines 100-141
```python
if intent.application_name:
    selectors.append(f'app="{intent.application_name}"')
for term in intent.search_terms[:3]:
    filters.append(f'|= "{term}"')
```
**Risk:** User input directly interpolated into LogQL without escaping. Input `"; malicious_query "` breaks out of quotes.
**Fix:** Escape `"` and `\` characters before interpolation.

---

### H5. Command Injection via Git Repository URL

**File:** `app/services/git_sync_service.py` — lines 43-56
```python
return repo_url.replace("https://", f"https://{self.token}@")
```
**Risk:** Token embedded in URL. If repo_url is user-controlled and contains special characters, credential leakage via logs/error messages. The URL is passed to subprocess for git clone.

---

### H6. WebSocket Token in Query Parameters

**File:** `app/routers/grafana_proxy.py` — lines 46-49
```python
token = websocket.cookies.get("access_token")
if not token:
    token = websocket.query_params.get("access_token")
```
**Risk:** Query parameter tokens appear in proxy logs, browser history, and referrer headers.

---

### H7. Missing Security Headers

**File:** `app/main.py` — middleware section
**Missing:**
- `X-Frame-Options: DENY` — clickjacking risk
- `X-Content-Type-Options: nosniff` — MIME sniffing risk
- `Strict-Transport-Security` — downgrade attacks
- `Content-Security-Policy` — XSS mitigation
- `Referrer-Policy` — information leakage

---

### H8. Missing CORS Configuration

**File:** `app/main.py`
No `CORSMiddleware` found. Default FastAPI behavior may allow cross-origin requests, enabling CSRF-like attacks from malicious websites.

---

## MEDIUM Findings

### M1. JWT Token — No Revocation/Blacklist
**File:** `app/services/auth_service.py` — line 132-142
24-hour token lifetime with no server-side revocation. If a token is compromised, it remains valid for up to 24 hours with no way to invalidate it.

### M2. Cookie Security — Missing Flags
**File:** `app/routers/auth.py` — lines 78-85
`samesite="lax"` (should be `"strict"`), no `secure=True` flag, no `Path` restriction.

### M3. No MFA/2FA
Password-only authentication. No TOTP, WebAuthn, or any second factor support.

### M4. Wide Dependency Version Ranges
**File:** `requirements.txt`
`langchain>=0.1.16,<0.3.0` spans 2 major versions. `asyncpg>=0.29.0` is completely unpinned. No lock file.

### M5. Unpinned Docker Base Image
**File:** `Dockerfile` — line 1
`python:3.11-slim` without digest pinning. Could pull different image contents on each build.

### M6. Atlas CLI — Unverified Download
**File:** `Dockerfile` — line 13
`curl -sSf https://atlasgo.sh | sh` — downloads and executes shell script without checksum verification.

### M7. SSH Key Stored Without Cleanup
**File:** `app/services/git_sync_service.py` — line 64
`tempfile.NamedTemporaryFile(delete=False)` — SSH key persists on disk after use.

### M8. Exposed Prometheus/Grafana Ports
**File:** `docker-compose.yml` — lines 92, 107
`9090:9090` and `3000:3000` exposed on all interfaces instead of `127.0.0.1` only.

### M9. PII Logs — No Access Audit
**File:** `app/routers/pii_logs.py` — line 86
Permission check exists but no audit logging for who accessed PII detection logs.

### M10. Presidio Configuration Gaps
**File:** `app/services/pii_service.py` — lines 52-68
`CRYPTO` entity disabled due to bug. `DATE_TIME` excluded. No custom entity recognizers.

### M11. Overly Permissive Runbook ACL
**File:** `app/services/auth_service.py` — lines 226-277
ADDITIVE permission model only — no deny/negative permissions possible.

### M12. `sslmode=disable` on Database Connection
**File:** `docker-compose.yml` — line 37
Database traffic unencrypted between application and PostgreSQL.

---

## OWASP Top 10 Mapping

| OWASP 2021 | Findings | Worst Severity |
|---|---|---|
| **A01: Broken Access Control** | Unauthenticated webhook (C1), optional auth on Grafana proxy (C2), unprotected config endpoints (H1), overly permissive ACL (M11) | **CRITICAL** |
| **A02: Cryptographic Failures** | Default JWT secret (C3), credentials in Git (C4), no encryption key rotation, `sslmode=disable` (M12) | **CRITICAL** |
| **A03: Injection** | SQL wildcard injection in 6+ routers (H3), LogQL injection (H4), command injection via git URL (H5) | **HIGH** |
| **A04: Insecure Design** | No account lockout (H2), no MFA (M3), ADDITIVE-only permissions (M11) | **HIGH** |
| **A05: Security Misconfiguration** | Missing security headers (H7), no CORS (H8), exposed ports (M8), default credentials (C3) | **HIGH** |
| **A06: Vulnerable Components** | Wide dependency ranges (M4), unverified Atlas download (M6), Presidio bugs (M10) | **MEDIUM** |
| **A07: Auth Failures** | No account lockout (H2), 5/min rate limit insufficient, no MFA (M3), 24hr JWT with no revocation (M1) | **HIGH** |
| **A08: Integrity Failures** | Unsigned downloads in Dockerfile (M6), no SBOM | **MEDIUM** |
| **A09: Logging Failures** | No audit on PII log access (M9), no structured security event logging | **MEDIUM** |
| **A10: SSRF** | Prometheus/Grafana proxy forwards arbitrary paths to internal services | **MEDIUM** |

---

## Remediation Priority Matrix

### Immediate (Block Deployment)

| # | Finding | Effort | Files to Change |
|---|---|---|---|
| 1 | Add auth to webhook endpoint | Small | `app/routers/webhook.py` |
| 2 | Fix Grafana proxy `get_current_user_optional` → `get_current_user` | Trivial | `app/routers/grafana_proxy.py` |
| 3 | Add auth to Prometheus config endpoints | Small | `app/routers/prometheus.py` |
| 4 | Remove `.env.local` from Git, add to `.gitignore` | Small | `.gitignore`, rotate secrets |
| 5 | Add startup validation rejecting default credentials | Small | `app/config.py` |

### This Sprint

| # | Finding | Effort | Files to Change |
|---|---|---|---|
| 6 | Add security headers middleware | Small | `app/main.py` |
| 7 | Configure CORS with explicit origin allowlist | Small | `app/main.py` |
| 8 | Escape SQL wildcards in all `ilike()` calls | Medium | 6+ router files |
| 9 | Escape LogQL interpolation | Small | `app/services/query_translator.py` |
| 10 | Implement account lockout | Medium | `app/routers/auth.py`, `app/services/auth_service.py` |
| 11 | Set `sslmode=require` on DATABASE_URL | Trivial | `docker-compose.yml` |
| 12 | Bind Prometheus/Grafana to `127.0.0.1` | Trivial | `docker-compose.yml` |

### Next Cycle

| # | Finding | Effort | Files to Change |
|---|---|---|---|
| 13 | Implement JWT revocation (Redis blacklist) | Medium | New middleware + Redis dependency |
| 14 | Add MFA/TOTP support | Large | Auth service + UI changes |
| 15 | Pin all dependency versions + add lock file | Medium | `requirements.txt` |
| 16 | Pin Docker base image with digest | Trivial | `Dockerfile` |
| 17 | Add PII access audit logging | Small | `app/routers/pii_logs.py` |
| 18 | Implement structured security event logging | Large | Cross-cutting concern |

---

## Compliance Impact

| Standard | Status | Key Gaps |
|---|---|---|
| **SOC 2 Type II** | Not Ready | Missing audit trail, no access reviews, no MFA, weak secrets management |
| **GDPR** | Partially Ready | PII detection exists but no comprehensive data subject access, no retention policies |
| **PCI-DSS** | Not Ready | Weak credential management, no encryption in transit (sslmode=disable), no segmentation |
| **ISO 27001** | Not Ready | Multiple gaps in access control (A.9), cryptography (A.10), operations security (A.12) |
| **HIPAA** | Not Ready | No audit controls, no access logging, no encryption enforcement |

---

## Sources

- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [Top 10 AIOps Tools for 2026 - Deepchecks](https://www.deepchecks.com/top-10-aiops-tools-2025/)
- [Best AIOps Platforms Reviews 2026 - Gartner Peer Insights](https://www.gartner.com/reviews/market/aiops-platforms)
- [Top 8 AIOps Vendors in 2026 - Aisera](https://aisera.com/blog/top-aiops-platforms/)
- [Top AIOps Tools and Platforms - TechTarget](https://www.techtarget.com/searchEnterpriseAI/tip/The-top-AIOps-tools-and-platforms-to-consider)
