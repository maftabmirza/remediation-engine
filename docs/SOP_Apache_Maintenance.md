# Standard Operating Procedure (SOP) - Apache Web Server Maintenance
**Effective Date:** 2024-01-01
**Scope:** Production Web Servers (`t-aiops-xx`)

## 1. Monitoring & Alerts
*   **Automated Alerting**: The AIOps system monitors Apache uptime via Prometheus.
*   **Alert Response**: If `ApacheDown` is triggered:
    1.  The AIOps engine will automatically create an incident.
    2.  Use the `[t-aiops-01] Web Service Restart` runbook to attempt a quick fix.
    3.  If that fails, proceed to **Manual Escalation**.

## 2. Maintenance Policy
> [!IMPORTANT]
> **Manual Escalation Policy**: For critical failures that cannot be resolved by the automated restart runbook, do **NOT** attempt further automated fixes.

*   **Who to Contact**: Shift Supervisor (Ext 1234) or On-Call DevOps Engineer.
*   **Notification Method**: Physical Phone Call or Pager. (Slack/Email integrations are currently disabled for critical escalation).
*   **Maintenance Window**: Tuesdays and Thursdays, 02:00 AM - 04:00 AM EST.

## 3. Routine Diagnostics
Before escalating, gather the following diagnostic info (The AI "Host Diagnostics Bundle" runbook does this automatically):
*   Current System Load (`uptime`)
*   Memory Usage (`free -h`)
*   Recent Error Logs (`tail /var/log/apache2/error.log`)
*   Active Connections (`netstat`)

## 4. Known Issues
*   **DB Connection Spikes**: If you see "Too many connections", restart the *Database Container*, not just Apache.
*   **Configuration Drift**: Ensure no one has manually edited `/etc/apache2/apache2.conf` without a Change Request.
