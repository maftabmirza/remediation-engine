# Test Environment Setup Guide

This directory contains the configuration and scripts to set up the **Lab Environment** on your target server (`15.204.233.209`).

## Overview

- **Target Server**: `15.204.233.209` (ubuntu / Passw0rd)
- **Role**: Simulates the "Production Infrastructure" that our AIOps platform will monitor and remediate.
- **Components**:
    -   **Nginx**: Web application (Port 8080).
    -   **Redis**: Database (Port 6379).
    -   **Node Exporter**: Host metrics (Port 9100).
    -   **Chaos Scripts**: Tools to break things intentionally.

## Step 1: Deploy to Lab VM

1.  **Copy Files**: Upload this entire `test-env` directory to the Lab VM.
    ```bash
    # From your local machine (or wherever this repo is checked out)
    scp -r test-env/ ubuntu@15.204.233.209:~/test-env
    ```

2.  **Run Setup**: SSH into the VM and run the setup script.
    ```bash
    ssh ubuntu@15.204.233.209
    cd ~/test-env
    bash setup_lab.sh
    ```
    *This script will install Docker, Node Exporter, and start the target containers.*

## Step 2: Verification

After setup, verify accessing the services from your browser or the AIOps server:
-   **Web App**: `http://15.204.233.209:8080`
-   **Metrics**: `http://15.204.233.209:9100/metrics`

## Step 3: Running Chaos Scenarios

To test the Remediation Engine, trigger failures on the Lab VM:

### Scenario 1: High CPU Load
Simulates a runaway process.
```bash
./chaos/cpu_stress.sh
```
*Expected Result*: Alert `HostHighCpuLoad` fires -> Remediation Engine analyzes -> Suggests "Check processes".

### Scenario 2: Service Crash
Simulates a container failure.
```bash
./chaos/stop_web.sh
```
*Expected Result*: Alert `TargetDown` fires -> Remediation Engine executes Runbook -> Restarts container -> Issue resolved.
