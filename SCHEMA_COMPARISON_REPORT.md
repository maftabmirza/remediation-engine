# Database Schema Comparison Report

**Comparing:**
1. `database_schema_20260125.sql` (WORKING/CORRECT schema)
2. `current_full_schema.sql` (CURRENT schema with issues)

**Generated:** January 26, 2026

---

## 🔴 CRITICAL DIFFERENCES - Priority Tables

### 1. `agent_steps` Table

| Column | WORKING Schema | CURRENT Schema | Issue |
|--------|----------------|----------------|-------|
| `blocked_reason` | `character varying(500)` | `text` | **TYPE MISMATCH** - Current uses TEXT instead of VARCHAR(500) |

**Fix Required:**
```sql
ALTER TABLE agent_steps ALTER COLUMN blocked_reason TYPE character varying(500);
```

---

### 2. `agent_sessions` Table

✅ **NO DIFFERENCES FOUND** - Both schemas match exactly.

---

### 3. `agent_audit_logs` Table

✅ **NO COLUMN DIFFERENCES FOUND** - Both schemas match exactly.

**INDEX DIFFERENCES:**

| Index Name | WORKING Schema | CURRENT Schema |
|------------|----------------|----------------|
| `idx_audit_created` | ✅ EXISTS (`created_at`) | ❌ MISSING |
| `idx_audit_user` | ✅ EXISTS (`user_id`) | ❌ MISSING |
| `idx_audit_user_created` | ❌ NOT EXISTS | ⚠️ EXTRA (`user_id, created_at`) |
| `ix_agent_audit_logs_created_at` | ❌ NOT EXISTS | ⚠️ EXTRA (`created_at`) |

**Issues:**
- WORKING has separate indexes: `idx_audit_created` and `idx_audit_user`
- CURRENT has a composite index `idx_audit_user_created` and also `ix_agent_audit_logs_created_at`

**Fix Required:**
```sql
-- Add missing indexes
CREATE INDEX idx_audit_created ON public.agent_audit_logs USING btree (created_at);
CREATE INDEX idx_audit_user ON public.agent_audit_logs USING btree (user_id);

-- Optionally remove extra indexes (evaluate performance impact first)
DROP INDEX IF EXISTS idx_audit_user_created;
DROP INDEX IF EXISTS ix_agent_audit_logs_created_at;
```

---

### 4. `agent_rate_limits` Table

**COLUMN ORDER DIFFERENCE:**

| WORKING Schema Order | CURRENT Schema Order |
|---------------------|---------------------|
| 1. id | 1. id |
| 2. user_id | 2. user_id |
| 3. commands_this_minute | 3. commands_this_minute |
| 4. **minute_window_start** | 4. **sessions_this_hour** |
| 5. sessions_this_hour | 5. minute_window_start |
| 6. hour_window_start | 6. hour_window_start |
| ... | ... |

**Note:** Column order difference is cosmetic and does not affect functionality.

**EXTRA INDEX IN CURRENT:**

| Index Name | WORKING Schema | CURRENT Schema |
|------------|----------------|----------------|
| `ix_agent_rate_limits_user_id` | ❌ NOT EXISTS | ⚠️ EXTRA |

**Fix Required (optional - evaluate performance):**
```sql
-- Remove extra index if not needed
DROP INDEX IF EXISTS ix_agent_rate_limits_user_id;
```

---

## 🟠 OTHER TABLE DIFFERENCES

### 5. `ai_feedback` Table

**COLUMN ORDER DIFFERENCE:**

| WORKING Schema | CURRENT Schema |
|----------------|----------------|
| id | id |
| user_id | created_at |
| session_id | message_id |
| runbook_id | runbook_id |
| message_id | session_id |
| created_at | user_id |

**Note:** Column order difference only - no type mismatches.

---

### 6. `ai_helper_audit_logs` Table

**SIGNIFICANT DIFFERENCES:**

| Aspect | WORKING Schema | CURRENT Schema |
|--------|----------------|----------------|
| `ai_suggested_action` | `character varying(100)` | `character varying` (unlimited) |
| `user_action` | `character varying(50)` | `character varying` (unlimited) |
| `execution_result` | `character varying(50)` | `character varying` (unlimited) |
| `executed` default | No default | `DEFAULT false` |
| `action_blocked` default | No default | `DEFAULT false` |
| `permission_checked` default | No default | `DEFAULT true` |
| `is_error` default | No default | `DEFAULT false` |
| CHECK constraints | ✅ `ck_ai_audit_execution_result` | ❌ MISSING |
| CHECK constraints | ✅ `ck_ai_audit_user_action` | ❌ MISSING |

**MISSING CONSTRAINTS in CURRENT:**
```sql
CONSTRAINT ck_ai_audit_execution_result CHECK (((execution_result)::text = ANY ((ARRAY['success', 'failed', 'blocked', 'timeout'])::text[])))
CONSTRAINT ck_ai_audit_user_action CHECK (((user_action)::text = ANY ((ARRAY['approved', 'rejected', 'modified', 'ignored', 'pending'])::text[])))
```

**Fix Required:**
```sql
-- Fix column types
ALTER TABLE ai_helper_audit_logs ALTER COLUMN ai_suggested_action TYPE character varying(100);
ALTER TABLE ai_helper_audit_logs ALTER COLUMN user_action TYPE character varying(50);
ALTER TABLE ai_helper_audit_logs ALTER COLUMN execution_result TYPE character varying(50);

-- Add missing constraints
ALTER TABLE ai_helper_audit_logs ADD CONSTRAINT ck_ai_audit_execution_result 
    CHECK (((execution_result)::text = ANY ((ARRAY['success', 'failed', 'blocked', 'timeout'])::text[])));
ALTER TABLE ai_helper_audit_logs ADD CONSTRAINT ck_ai_audit_user_action 
    CHECK (((user_action)::text = ANY ((ARRAY['approved', 'rejected', 'modified', 'ignored', 'pending'])::text[])));
```

---

### 7. `ai_helper_sessions` Table

**DIFFERENCES:**

| Aspect | WORKING Schema | CURRENT Schema |
|--------|----------------|----------------|
| Column order | Different | Different |
| `status` default | No inline default | `DEFAULT 'active'` |
| `session_type` default | No inline default | `DEFAULT 'general'` |
| `total_queries` default | No inline default | `DEFAULT 0` |
| `total_tokens_used` default | No inline default | `DEFAULT 0` |
| `total_cost_usd` default | No inline default | `DEFAULT '0'` |
| CHECK constraints | ✅ `ck_ai_session_status` | ❌ MISSING |
| CHECK constraints | ✅ `ck_ai_session_type` | ❌ MISSING |

**MISSING CONSTRAINTS in CURRENT:**
```sql
CONSTRAINT ck_ai_session_status CHECK (((status)::text = ANY ((ARRAY['active', 'completed', 'abandoned', 'error'])::text[])))
CONSTRAINT ck_ai_session_type CHECK (((session_type)::text = ANY ((ARRAY['general', 'form_assistance', 'troubleshooting', 'learning'])::text[])))
```

---

### 8. `alert_correlations` Table

**MAJOR STRUCTURAL DIFFERENCES:**

| Column | WORKING Schema | CURRENT Schema |
|--------|----------------|----------------|
| `related_alert_id` | ❌ NOT EXISTS | `uuid NOT NULL` (EXTRA) |
| `correlation_type` | ❌ NOT EXISTS | `varchar(50) NOT NULL` (EXTRA) |
| `correlation_score` | ❌ NOT EXISTS | `double precision NOT NULL` (EXTRA) |
| `root_cause_analysis` | `text` | ❌ MISSING |
| `confidence_score` | `double precision` | ❌ MISSING |
| `summary` default | No default | `DEFAULT 'Auto Correlation'` |

**⚠️ WARNING:** This table has significantly different structure between schemas!

**Fix Required:**
```sql
-- Add missing columns
ALTER TABLE alert_correlations ADD COLUMN root_cause_analysis text;
ALTER TABLE alert_correlations ADD COLUMN confidence_score double precision;

-- Remove extra columns (if safe)
ALTER TABLE alert_correlations DROP COLUMN related_alert_id;
ALTER TABLE alert_correlations DROP COLUMN correlation_type;
ALTER TABLE alert_correlations DROP COLUMN correlation_score;

-- Fix summary default
ALTER TABLE alert_correlations ALTER COLUMN summary DROP DEFAULT;
```

---

## 🟡 INDEX DIFFERENCES SUMMARY

### Extra Indexes in CURRENT (not in WORKING):
| Index Name | Table | Columns |
|------------|-------|---------|
| `ix_agent_audit_logs_created_at` | agent_audit_logs | created_at |
| `ix_agent_rate_limits_user_id` | agent_rate_limits | user_id |
| `idx_audit_user_created` | agent_audit_logs | user_id, created_at |

### Missing Indexes in CURRENT (exist in WORKING):
| Index Name | Table | Columns |
|------------|-------|---------|
| `idx_audit_created` | agent_audit_logs | created_at |
| `idx_audit_user` | agent_audit_logs | user_id |

---

## 📋 COMPLETE FIX SCRIPT

```sql
-- ============================================
-- FIX SCRIPT: Align current_full_schema to database_schema_20260125
-- ============================================

-- 1. Fix agent_steps.blocked_reason type
ALTER TABLE agent_steps ALTER COLUMN blocked_reason TYPE character varying(500);

-- 2. Fix ai_helper_audit_logs column types
ALTER TABLE ai_helper_audit_logs ALTER COLUMN ai_suggested_action TYPE character varying(100);
ALTER TABLE ai_helper_audit_logs ALTER COLUMN user_action TYPE character varying(50);
ALTER TABLE ai_helper_audit_logs ALTER COLUMN execution_result TYPE character varying(50);

-- 3. Add missing CHECK constraints for ai_helper_audit_logs
ALTER TABLE ai_helper_audit_logs ADD CONSTRAINT ck_ai_audit_execution_result 
    CHECK (((execution_result)::text = ANY ((ARRAY['success'::varchar, 'failed'::varchar, 'blocked'::varchar, 'timeout'::varchar])::text[])));
ALTER TABLE ai_helper_audit_logs ADD CONSTRAINT ck_ai_audit_user_action 
    CHECK (((user_action)::text = ANY ((ARRAY['approved'::varchar, 'rejected'::varchar, 'modified'::varchar, 'ignored'::varchar, 'pending'::varchar])::text[])));

-- 4. Add missing CHECK constraints for ai_helper_sessions
ALTER TABLE ai_helper_sessions ADD CONSTRAINT ck_ai_session_status 
    CHECK (((status)::text = ANY ((ARRAY['active'::varchar, 'completed'::varchar, 'abandoned'::varchar, 'error'::varchar])::text[])));
ALTER TABLE ai_helper_sessions ADD CONSTRAINT ck_ai_session_type 
    CHECK (((session_type)::text = ANY ((ARRAY['general'::varchar, 'form_assistance'::varchar, 'troubleshooting'::varchar, 'learning'::varchar])::text[])));

-- 5. Fix agent_audit_logs indexes
DROP INDEX IF EXISTS idx_audit_user_created;
CREATE INDEX IF NOT EXISTS idx_audit_created ON public.agent_audit_logs USING btree (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_user ON public.agent_audit_logs USING btree (user_id);

-- 6. Fix alert_correlations structure (CAUTION: Verify data migration needs!)
-- ALTER TABLE alert_correlations ADD COLUMN IF NOT EXISTS root_cause_analysis text;
-- ALTER TABLE alert_correlations ADD COLUMN IF NOT EXISTS confidence_score double precision;
-- WARNING: Dropping columns may cause data loss
-- ALTER TABLE alert_correlations DROP COLUMN IF EXISTS related_alert_id;
-- ALTER TABLE alert_correlations DROP COLUMN IF EXISTS correlation_type;
-- ALTER TABLE alert_correlations DROP COLUMN IF EXISTS correlation_score;

-- ============================================
-- END FIX SCRIPT
-- ============================================
```

---

## 📊 SUMMARY

| Category | Count |
|----------|-------|
| **Column Type Mismatches** | 4 |
| **Missing Columns** | 2 |
| **Extra Columns** | 3 |
| **Missing Constraints** | 4 |
| **Missing Indexes** | 2 |
| **Extra Indexes** | 3 |
| **Column Order Differences** | 3 tables |

### Priority Actions:
1. 🔴 **HIGH:** Fix `agent_steps.blocked_reason` type (VARCHAR(500) not TEXT)
2. 🔴 **HIGH:** Fix `ai_helper_audit_logs` column types and constraints
3. 🟠 **MEDIUM:** Fix `ai_helper_sessions` constraints
4. 🟠 **MEDIUM:** Fix index discrepancies on `agent_audit_logs`
5. 🟡 **LOW:** Evaluate `alert_correlations` structural differences (may be intentional)
