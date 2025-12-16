---
description: Deploy application to a new server
---

# Deployment Workflow

This workflow ensures reliable deployment to a new server.

## Prerequisites
- Docker and Docker Compose installed on target server
- SSH access to target server
- Git repository access

## Pre-Deployment Checks (Local)

// turbo
1. Check for uncommitted changes:
```bash
git status
```

2. Commit all changes if needed:
```bash
git add -A
git commit -m "Pre-deployment: commit all changes"
git push origin <branch>
```

// turbo
3. Verify requirements.txt has pgvector:
```bash
grep pgvector requirements.txt
```

// turbo
4. Verify docker-compose uses pgvector image:
```bash
grep "pgvector/pgvector" docker-compose.yml
```

## Server Deployment

5. Connect to server:
```bash
ssh user@server
cd /path/to/aiops-platform
```

6. Pull latest code (force reset to avoid conflicts):
```bash
git fetch origin
git reset --hard origin/<branch>
```

7. Build and start containers:
```bash
docker-compose build --no-cache remediation-engine
docker-compose up -d
```

## Post-Deployment Verification

// turbo
8. Check container status:
```bash
docker ps | grep -E "postgres|remediation"
```

9. Check for startup errors:
```bash
docker logs --tail 50 remediation-engine
```

// turbo
10. Verify migrations applied:
```bash
docker exec remediation-engine alembic current
```

11. Test key pages are accessible:
- Dashboard: http://server:8080/
- Alerts: http://server:8080/alerts
- Runbooks: http://server:8080/runbooks
- Knowledge: http://server:8080/knowledge
- Applications: http://server:8080/applications

## Troubleshooting

### Container in restart loop
```bash
docker logs remediation-engine
```
Check for:
- ImportError: Missing packages in requirements.txt
- ModuleNotFoundError: Missing router registrations in main.py
- Migration errors: Check alembic migration chain

### Migration errors
```bash
# Stamp current database state and retry
docker exec remediation-engine alembic stamp head
docker-compose restart remediation-engine
```

### Permission denied on entrypoint.sh
```bash
chmod +x entrypoint.sh
docker-compose build --no-cache remediation-engine
```
