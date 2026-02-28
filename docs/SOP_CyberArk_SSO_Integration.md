# Standard Operating Procedure (SOP) — CyberArk Identity SSO Integration

| Field | Value |
|---|---|
| **Document ID** | SOP-SEC-001 |
| **Effective Date** | 2026-02-26 |
| **Version** | 1.0 |
| **Author** | Platform Security Team |
| **Reviewed By** | IAM / CyberArk Admin |
| **Scope** | AIOps Remediation Engine — All environments |
| **Classification** | Internal — Security Compliance |

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [How It Works — Architecture Overview](#2-how-it-works--architecture-overview)
3. [Prerequisites](#3-prerequisites)
4. [Step-by-Step: CyberArk Admin Setup](#4-step-by-step-cyberark-admin-setup)
5. [Step-by-Step: App Configuration (System Settings)](#5-step-by-step-app-configuration-system-settings)
6. [Role Mapping Reference](#6-role-mapping-reference)
7. [User Login Flow](#7-user-login-flow)
8. [Testing & Validation Checklist](#8-testing--validation-checklist)
9. [Rollback Procedure](#9-rollback-procedure)
10. [Troubleshooting](#10-troubleshooting)
11. [Security Notes & Compliance](#11-security-notes--compliance)
12. [Contact & Escalation](#12-contact--escalation)

---

## 1. Purpose & Scope

This SOP describes how to configure the AIOps Remediation Engine to accept user logins via **CyberArk Identity (SAML 2.0 SSO)**.

### Why this is needed

Security compliance requires that privileged application access be brokered through the corporate Identity Provider (CyberArk Identity). Users authenticate once at the CyberArk portal, are mapped to an application role by their CyberArk group membership, and are redirected into the app — **without entering a separate username and password**.

### What does NOT change

- **Local login (`/api/auth/login`) is not removed.** It remains available for service accounts and emergency admin access.
- Existing local users continue to work unchanged.
- All downstream RBAC, permissions, audit logging, and JWT behaviour is identical for SSO and local users.
- SSO is **completely dormant** until explicitly configured by an admin.

---

## 2. How It Works — Architecture Overview

```
User Browser
     │
     │  1. Click "Login with CyberArk"
     ▼
GET /api/auth/saml/login
     │
     │  2. App builds SAML AuthnRequest, redirects to CyberArk
     ▼
CyberArk Identity Portal
     │
     │  3. User authenticates (password, MFA, etc.)
     │  4. CyberArk POSTs signed SAML assertion to ACS URL
     ▼
POST /api/auth/saml/acs
     │
     │  5. App validates signature, extracts NameID + attributes
     │  6. Find/create local User record
     │  7. Map CyberArk group → app role
     │  8. Issue JWT + HttpOnly cookie (same as local login)
     ▼
User lands on app dashboard, fully authenticated
```

**Key URLs**

| Purpose | URL |
|---|---|
| SP-initiated login | `GET /api/auth/saml/login` |
| Assertion Consumer Service (ACS) | `POST /api/auth/saml/acs` |
| SP Metadata XML (for CyberArk admin) | `GET /api/auth/saml/metadata` |
| SSO status check | `GET /api/auth/saml/status` |
| Local login (unchanged) | `POST /api/auth/login` |

---

## 3. Prerequisites

### App team prerequisites

- [ ] AIOps Remediation Engine running on `security-2.0` branch or later
- [ ] Database migration `20260226000000_add_sso_fields` applied (verify: `GET /api/auth/saml/status` returns `200`)
- [ ] Public HTTPS URL for the app is known (e.g. `https://aiops.company.com`)
- [ ] Admin account to access **Settings → Auth Settings**

### CyberArk admin prerequisites

- [ ] Access to **CyberArk Identity Admin Portal** (`https://your-tenant.cyberark.cloud`)
- [ ] Permission to create Web Applications / SAML Apps in the tenant
- [ ] Knowledge of which AD/CyberArk groups should map to which app roles
- [ ] (Optional) CyberArk tenant metadata URL or XML export capability

---

## 4. Step-by-Step: CyberArk Admin Setup

> **Performed by:** CyberArk / IAM Administrator
> **Estimated time:** 20–30 minutes

### 4.1 Create a new SAML Web Application

1. Log in to **CyberArk Identity Admin Portal**
2. Navigate to **Apps & Widgets → Web Apps → Add Web App**
3. Select **SAML** as the app type
4. Name it: `AIOps Remediation Engine` (or your preferred name)

### 4.2 Configure SP settings

In the SAML tab of the new app, configure:

| CyberArk Field | Value |
|---|---|
| **SP Entity ID** | `https://aiops.company.com/api/auth/saml/metadata` |
| **ACS URL** | `https://aiops.company.com/api/auth/saml/acs` |
| **Name ID Format** | `emailAddress` |
| **Name ID Value** | User's email address |
| **Binding** | `HTTP-POST` |

> Replace `aiops.company.com` with your actual public domain.
>
> **Tip**: You can import these settings automatically by giving CyberArk the SP Metadata XML.  
> Download it at: `GET https://aiops.company.com/api/auth/saml/metadata` (available once app is running).

### 4.3 Configure SAML attribute assertions

Add the following attribute statements so the app can identify users and assign roles:

| Attribute Name | Source | Example Value |
|---|---|---|
| `email` | User attribute: `Email` | `john.doe@company.com` |
| `username` | User attribute: `Username` or `sAMAccountName` | `john.doe` |
| `role` | Role/Group membership | `CyberArk_Admins` |

> The attribute names (`email`, `username`, `role`) are configurable in the app. See Section 5 — Attribute Mapping.

### 4.4 Assign users / groups to the app

1. In the **Permissions** tab, assign the relevant CyberArk groups to this app
2. Suggested group structure (adapt to your tenant):

| CyberArk Group | Recommended App Role |
|---|---|
| `AIOps_Admins` | `admin` |
| `AIOps_Operators` | `operator` |
| `AIOps_Viewers` | `viewer` |
| `AIOps_Auditors` | `auditor` |
| `AIOps_SecurityAdmins` | `security_admin` |

### 4.5 Export IdP Metadata

1. Go to the **Trust** tab of the SAML app
2. Click **Download Metadata** or copy the **Metadata URL**
3. Provide **either** the metadata URL or the downloaded XML to the app administrator

---

## 5. Step-by-Step: App Configuration (System Settings)

> **Performed by:** AIOps Platform Administrator
> **Estimated time:** 10 minutes

### 5.1 Navigate to Auth Settings

1. Log in to the AIOps app with an **admin** account
2. Go to **Settings** (gear icon in the sidebar)
3. Click **Auth Settings** in the left navigation

### 5.2 Select CyberArk Identity method

1. In the **Authentication Method** dropdown, select **CyberArk Identity (SAML 2.0)**
2. The CyberArk configuration panel expands (shown in green)

### 5.3 Fill in Service Provider details

These identify **your app** to CyberArk:

| Field | Value |
|---|---|
| **SP Entity ID** | `https://aiops.company.com/api/auth/saml/metadata` |
| **ACS URL** | `https://aiops.company.com/api/auth/saml/acs` |

> These must match exactly what was entered in CyberArk Step 4.2.

### 5.4 Fill in Identity Provider details

Provide **one** of the following from the CyberArk admin (Section 4.5):

| Option | Field | Example |
|---|---|---|
| **URL (preferred)** | IdP Metadata URL | `https://your-tenant.cyberark.cloud/saml/metadata/abc123` |
| **XML (fallback)** | IdP Metadata XML | Paste the raw XML content |

### 5.5 Configure Attribute Mapping

Map CyberArk SAML attribute names to app fields:

| Field | Default | Change if CyberArk uses a different attribute name |
|---|---|---|
| **Email Attribute** | `email` | e.g. `mail` or `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` |
| **Username Attribute** | `username` | e.g. `sAMAccountName` |
| **Role/Group Attribute** | `role` | e.g. `memberOf` or `groups` |

### 5.6 Configure Role Mapping

In the **Role Mapping** JSON editor, map CyberArk group names to app roles:

```json
{
  "AIOps_Admins": "admin",
  "AIOps_Operators": "operator",
  "AIOps_Viewers": "viewer",
  "AIOps_Auditors": "auditor",
  "AIOps_SecurityAdmins": "security_admin"
}
```

Available app roles:

| Role | Capabilities |
|---|---|
| `owner` | Full control including user management |
| `admin` | Full control including user management |
| `maintainer` | Manage servers, providers; execute runbooks |
| `operator` | Execute runbooks, read resources |
| `viewer` | Read-only access |
| `auditor` | Read + audit log access |
| `security_admin` | PII config + audit access |
| `security_viewer` | PII config read + logs |

### 5.7 Set Default Role and Auto-Provision

| Setting | Recommended Value | Notes |
|---|---|---|
| **Default Role** | `viewer` | Assigned when no role_mapping matches |
| **Auto-provision new users** | ✅ Enabled | Creates a local user on first SSO login |

> If auto-provision is **disabled**, SSO users must be pre-created in the app by an admin before they can log in.

### 5.8 Save and verify

1. Click **Save Auth Settings**
2. Click **Check SSO Status** — should show `SSO is active` with your SP entity ID
3. Click **Download SP Metadata XML** — share this with the CyberArk admin to confirm SP registration matches

---

## 6. Role Mapping Reference

### How role mapping works

When a user logs in via CyberArk, the SAML assertion includes their group membership (e.g. `AIOps_Ops,AIOps_Viewers`). The app:

1. Splits the value by comma if multiple groups are present
2. Looks up each group in the `role_mapping` config
3. Picks the **highest-privilege matched role** from the list
4. If no match is found, assigns the `default_role`
5. The role is **re-evaluated on every login** — CyberArk is always the source of truth

### Priority order (highest → lowest)

```
owner → admin → security_admin → maintainer → operator →
security_viewer → auditor → viewer
```

### Example

CyberArk sends: `role = "AIOps_Ops,AIOps_Viewers"`

Role mapping config:
```json
{ "AIOps_Ops": "operator", "AIOps_Viewers": "viewer" }
```

Result: `operator` (higher priority than `viewer`)

---

## 7. User Login Flow

### For end users (once SSO is configured)

1. Navigate to `https://aiops.company.com`
2. Click **"Login with CyberArk"** on the login page
3. Redirected to CyberArk Identity portal
4. Authenticate with corporate credentials + MFA
5. Redirected back to AIOps — logged in automatically
6. Role and permissions are applied based on CyberArk group membership

### For service accounts / emergency admin

- Use the standard **username + password** form on the login page
- Local login always remains available — it is never disabled by SSO configuration

### First-time SSO login (auto-provisioned user)

- A new local user record is created automatically
- Username is derived from the `username` SAML attribute
- Role is assigned from role mapping
- An audit log entry `sso_user_provisioned` is recorded
- Subsequent logins find the existing record by `sso_subject` (CyberArk NameID)

---

## 8. Testing & Validation Checklist

### Before go-live

- [ ] `GET /api/auth/saml/status` returns `{"enabled": true, "sp_entity_id": "..."}` 
- [ ] `GET /api/auth/saml/metadata` returns valid XML (HTTP 200, `Content-Type: application/xml`)
- [ ] SP metadata XML matches what is registered in CyberArk
- [ ] Test login with a **non-admin** CyberArk user — verify correct role is assigned
- [ ] Test login with a user in **multiple groups** — verify highest-priority role wins
- [ ] Test login with a user in **no mapped group** — verify `default_role` is assigned
- [ ] Verify audit log entry appears in **Settings → Audit Logs** after SSO login
- [ ] Verify local admin login still works with username/password
- [ ] Verify SSO user can access only resources permitted by their role

### API smoke test

```bash
# Check SSO is active
curl https://aiops.company.com/api/auth/saml/status

# Download SP metadata (should return XML)
curl -o sp-metadata.xml https://aiops.company.com/api/auth/saml/metadata

# Initiate login (should redirect to CyberArk)
curl -I https://aiops.company.com/api/auth/saml/login
# Expected: HTTP 302 Location: https://your-tenant.cyberark.cloud/...
```

---

## 9. Rollback Procedure

To revert to local authentication without rebuilding or redeploying:

### Via System Settings (preferred)

1. Go to **Settings → Auth Settings**
2. Change **Authentication Method** back to **Local Database (Default)**
3. Click **Save Auth Settings**
4. SSO endpoints immediately return `503` — no user can log in via CyberArk
5. All local accounts work instantly

### Via API (emergency / scripted)

```bash
curl -X POST https://aiops.company.com/api/auth/config \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"method": "local"}'
```

### What rollback does NOT affect

- Existing SSO-provisioned users remain in the database (`auth_provider = "cyberark"`)
- Their accounts become inaccessible via SSO but remain in the DB
- To re-enable their access, set a password for them via **Settings → Users → Reset Password**

---

## 10. Troubleshooting

### "CyberArk SSO is not configured" (503)

**Cause:** Auth method is not set to `cyberark_saml`, or config was not saved.  
**Fix:** Go to **Settings → Auth Settings**, select CyberArk Identity, fill fields, click Save.

---

### "Failed to fetch CyberArk IdP metadata from URL" (500)

**Cause:** The `idp_metadata_url` is unreachable from the app container.  
**Fix:**
1. Check that the URL is correct (provided by CyberArk admin)
2. Check network/firewall rules — the app container must reach the CyberArk tenant URL
3. As a fallback: paste the raw **IdP Metadata XML** in the Settings panel instead

---

### "CyberArk SAML authentication failed: invalid_response" (401)

**Cause:** Assertion signature validation failed.  
**Common reasons:**
- SP Entity ID in CyberArk does not match the one in app config
- ACS URL in CyberArk does not match `/api/auth/saml/acs`
- Clock skew between app server and CyberArk (>5 minutes)

**Fix:** Cross-check SP Entity ID and ACS URL between CyberArk app config and Settings panel. Ensure server time is synced (NTP).

---

### "CyberArk SAML response did not include a NameID" (400)

**Cause:** CyberArk is not configured to send a Name ID in the assertion.  
**Fix:** In CyberArk app config, ensure **Name ID Format** = `emailAddress` and **Name ID Value** is mapped to the user's email.

---

### User logs in successfully but has wrong role

**Cause:** Role mapping mismatch or attribute name incorrect.  
**Fix:**
1. Check the `attribute_role` field — ensure it matches the exact attribute name CyberArk sends
2. Check `role_mapping` — ensure the group name matches exactly (case-sensitive)
3. Contact CyberArk admin to confirm what value is being sent in the SAML assertion

**Debug tip:** Add a test user to a known group, log in, check **Settings → Audit Logs** for the `sso_login` event which will show the resolved role.

---

### User cannot auto-provision ("does not have a local account")

**Cause:** `auto_provision` is set to `false`.  
**Fix:** Either enable auto-provision in Settings, or pre-create the user in **Settings → Users** using their CyberArk email as the username.

---

### "python3-saml is not installed" (500)

**Cause:** Docker image was not rebuilt after the `security-2.0` changes.  
**Fix:** Rebuild and restart:
```bash
docker compose build remediation-engine
docker compose up -d remediation-engine
```

---

## 11. Security Notes & Compliance

| Requirement | How it is met |
|---|---|
| Centralised identity management | Authentication delegated to CyberArk Identity — no passwords stored for SSO users |
| MFA enforcement | Enforced by CyberArk Identity policy — the app has no bypass |
| Least-privilege access | Role assigned from CyberArk group — updated on every login |
| Audit trail | Every SSO login creates an `AuditLog` entry with user ID, IP, and action |
| Local account preservation | Local login not disabled — service accounts and emergency admin always available |
| Session security | JWT (HttpOnly cookie, 24h expiry) — identical to local login sessions |
| Signature validation | SAML assertion signature validated using CyberArk IdP certificate before any user data is trusted |
| SSO user isolation | SSO users cannot use password login — `password_hash` is set to a cryptographically random unusable value |

---

## 12. Contact & Escalation

| Role | Responsibility | Contact |
|---|---|---|
| **CyberArk / IAM Admin** | Create/configure SAML app in CyberArk, manage group assignments, export metadata | *(fill in)* |
| **Platform Admin** | Configure auth settings in AIOps, manage role mappings, user provisioning | *(fill in)* |
| **Security Team** | Compliance review, audit log review | *(fill in)* |
| **DevOps / SRE** | Rebuild/deploy container, debug network/firewall issues | *(fill in)* |

### Escalation path

1. Check **`GET /api/auth/saml/status`** — quick health check
2. Check **Settings → Audit Logs** — review recent SSO events
3. Check container logs: `docker compose logs --tail=100 remediation-engine`
4. Contact CyberArk admin to verify assertion contents with an IdP trace

---

*Document end — SOP-SEC-001 v1.0*
