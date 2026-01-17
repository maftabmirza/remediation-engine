# Production Deployment Checklist

## 🔒 Security Validation Checklist

Before deploying to production, verify ALL items below:

### 1. **Environment Configuration**
- [ ] `TESTING=false` (or not set at all)
- [ ] `DEBUG=false` 
- [ ] Production database credentials configured
- [ ] JWT_SECRET is strong and unique (not the test value)
- [ ] ENCRYPTION_KEY is production-grade (not test value)
- [ ] No environment variables contain "test" in their values

### 2. **Docker Build Verification**
```bash
# Build production image
docker build -t aiops-prod -f Dockerfile .

# Verify tests/ directory is NOT in the image
docker run --rm aiops-prod ls -la / | grep -q tests && echo "❌ FAIL: tests found" || echo "✅ PASS: no tests"

# Verify pytest.ini is NOT in the image  
docker run --rm aiops-prod ls -la / | grep -q pytest.ini && echo "❌ FAIL: pytest.ini found" || echo "✅ PASS: no pytest.ini"

# Run security checks inside container
docker run --rm aiops-prod python -m app.security_checks
```

### 3. **Code Verification**
- [ ] `.dockerignore` exists and excludes `tests/`
- [ ] `Dockerfile` does NOT copy `tests/` or `pytest.ini`
- [ ] No `conftest.py` in production image
- [ ] No test utilities imported in production code

### 4. **Database Integrity**
- [ ] `Application.name` has `unique=True` constraint
- [ ] `GrafanaDatasource.name` has `unique=True` constraint  
- [ ] Production migrations do NOT drop unique constraints
- [ ] Test-specific constraint relaxation is ONLY in `tests/conftest.py`

### 5. **Application Startup**
- [ ] Security checks run at startup (see `app/main.py`)
- [ ] Rate limiting is ENABLED (not disabled for tests)
- [ ] Background jobs start (scheduler, workers)
- [ ] No test fixtures or mock data loaded

### 6. **Runtime Verification**
```bash
# After deployment, verify from inside running container:
docker exec <container-id> python -m app.security_checks

# Check application logs for security check output:
docker logs <container-id> | grep "security checks"
```

### 7. **Automated CI/CD Gates**
Add these checks to your CI/CD pipeline:

```yaml
# .github/workflows/deploy.yml or .gitlab-ci.yml
production-security-check:
  script:
    - docker build -t test-prod-build .
    - docker run --rm -e TESTING=false test-prod-build python -m app.security_checks
    - docker run --rm test-prod-build sh -c "[ ! -d tests ] || exit 1"
```

## 🚨 If Any Check Fails

**DO NOT DEPLOY TO PRODUCTION**

1. Fix the issue in the codebase
2. Re-run all checks
3. Review deployment configuration
4. Verify with team lead before proceeding

## ✅ Post-Deployment Verification

After deployment to production:

1. **Check application logs:**
   ```bash
   # Should see: "✅ Production security checks passed"
   kubectl logs -f <pod-name> | grep security
   ```

2. **Verify database constraints:**
   ```sql
   -- Connect to production database
   SELECT conname, contype 
   FROM pg_constraint 
   WHERE conrelid = 'applications'::regclass 
   AND contype = 'u';  -- unique constraints
   ```

3. **Test rate limiting:**
   ```bash
   # Should be blocked after 5 attempts
   for i in {1..10}; do 
     curl -X POST https://prod.example.com/api/auth/login \
       -d '{"username":"test","password":"wrong"}'
   done
   ```

4. **Verify no test endpoints accessible:**
   ```bash
   curl https://prod.example.com/test
   # Should return 404
   ```

## 📋 Regular Audits

- [ ] Weekly: Review container images for test artifacts
- [ ] Monthly: Audit environment variables
- [ ] Quarterly: Full security review of deployment process
- [ ] After each major update: Re-run full checklist

---

**Last Updated:** January 17, 2026
**Reviewed By:** _______________
**Approved By:** _______________
