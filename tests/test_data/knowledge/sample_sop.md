# Nginx Service Management SOP

## Purpose
This Standard Operating Procedure (SOP) provides guidelines for managing and troubleshooting Nginx web server in production environments.

## Scope
This document applies to all Linux-based servers running Nginx in production, staging, and development environments.

## Prerequisites
- SSH access to the target server
- Sudo privileges
- Basic understanding of Nginx configuration

## Common Operations

### 1. Checking Nginx Status

```bash
sudo systemctl status nginx
```

**Expected Output**: Service should show as "active (running)"

### 2. Starting Nginx

```bash
sudo systemctl start nginx
```

### 3. Stopping Nginx

```bash
sudo systemctl stop nginx
```

### 4. Restarting Nginx

```bash
sudo systemctl restart nginx
```

**Note**: Use restart when you've made configuration changes.

### 5. Reloading Nginx Configuration

```bash
sudo systemctl reload nginx
```

**Note**: Reload is preferred over restart as it doesn't drop connections.

## Troubleshooting Guide

### Nginx Won't Start

**Symptoms**:
- `systemctl start nginx` fails
- Port 80 or 443 not listening

**Diagnosis Steps**:

1. Check configuration syntax:
   ```bash
   sudo nginx -t
   ```

2. Check error logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

3. Check if port is already in use:
   ```bash
   sudo netstat -tulpn | grep :80
   sudo netstat -tulpn | grep :443
   ```

4. Verify file permissions:
   ```bash
   ls -la /etc/nginx/nginx.conf
   ls -la /var/www/html
   ```

**Common Solutions**:

- **Configuration Error**: Fix syntax errors identified by `nginx -t`
- **Port Conflict**: Stop the conflicting process or change Nginx port
- **Permission Issues**: Ensure nginx user has access to web root
- **Missing SSL Certificates**: Verify SSL certificate paths in configuration

### Nginx Responding Slowly

**Symptoms**:
- High response times
- Connection timeouts

**Diagnosis Steps**:

1. Check server load:
   ```bash
   top
   htop
   uptime
   ```

2. Review access patterns:
   ```bash
   sudo tail -f /var/log/nginx/access.log
   ```

3. Check worker processes:
   ```bash
   ps aux | grep nginx
   ```

4. Review worker connections:
   ```bash
   sudo nginx -T | grep worker_connections
   ```

**Common Solutions**:

- Increase worker_processes in nginx.conf
- Increase worker_connections
- Enable caching
- Optimize backend application

### 502 Bad Gateway Errors

**Symptoms**:
- Users see "502 Bad Gateway" error page
- Upstream connection failures in logs

**Diagnosis Steps**:

1. Check upstream service status:
   ```bash
   # For application servers
   sudo systemctl status php-fpm   # For PHP apps
   sudo systemctl status gunicorn  # For Python apps
   ```

2. Verify upstream configuration:
   ```bash
   sudo nginx -T | grep upstream
   ```

3. Check firewall rules:
   ```bash
   sudo iptables -L
   ```

**Common Solutions**:

- Restart upstream application service
- Verify upstream server IP and port
- Check firewall allows connection to upstream
- Increase upstream timeout in nginx.conf

## Configuration Files

### Main Configuration
- **Location**: `/etc/nginx/nginx.conf`
- **Owner**: root:root
- **Permissions**: 644

### Site Configurations
- **Location**: `/etc/nginx/sites-available/`
- **Enabled Sites**: `/etc/nginx/sites-enabled/`

### Log Files
- **Access Log**: `/var/log/nginx/access.log`
- **Error Log**: `/var/log/nginx/error.log`

## Best Practices

1. **Always validate configuration** before reloading:
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

2. **Back up configuration** before making changes:
   ```bash
   sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d)
   ```

3. **Monitor logs regularly** for errors and anomalies

4. **Use reload instead of restart** to avoid dropping connections

5. **Test changes in staging** before applying to production

## Emergency Contacts

- **Infrastructure Team**: infrastructure@example.com
- **On-Call**: +1-555-ON-CALL
- **Escalation Manager**: ops-manager@example.com

## Related Documents

- [Nginx Configuration Guide](nginx-config-guide.md)
- [SSL Certificate Management](ssl-cert-management.md)
- [Load Balancer Setup](load-balancer-setup.md)

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-01 | DevOps Team | Initial version |
| 1.1 | 2025-01-15 | DevOps Team | Added 502 troubleshooting |
