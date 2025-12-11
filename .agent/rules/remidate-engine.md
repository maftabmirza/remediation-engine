---
trigger: always_on
---

Local development environment 
1. local code PS D:\remediate-engine-antigravity\remediation-engine>
2. Local windows container 
#d11204f9-edbb-44f8-82c8-b65eca2c6c58	Restart docker	queued	172.239.195.215	Auto	2m ago	2m 29s	
#4e85a1e7-55c6-428a-91f1-82a74212931c	Restart docker	queued	172.239.195.215	Auto	8m ago	8m 44s	

Important : We need to change code on local lapotop first, test , push to git and connect to 172.234.217.11 and pull, docker compose/restart and test 

Servers environment 
1.Remediate-engine container is running at 172.234.217.11
2, We can connect to usning user name aftab and container is running under /home/aftab/aiops-platform
3. There are few other container also running on same server as below
CONTAINER ID   IMAGE                               COMMAND                  CREATED        STATUS                  PORTS                                         NAMES
a3b57cb288cd   aiops-platform-remediation-engine   "uvicorn app.main:ap…"   6 hours ago    Up 12 minutes           0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   remediation-engine
37da439163fd   postgres:16-alpine                  "docker-entrypoint.s…"   26 hours ago   Up 26 hours (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp   aiops-postgres
dbab832e0b93   grafana/grafana:latest              "/run.sh"                5 days ago     Up 5 days               0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp   grafana
f31aa60d7f60   prom/alertmanager:v0.26.0           "/bin/alertmanager -…"   5 days ago     Up 5 days (healthy)     0.0.0.0:9093->9093/tcp, [::]:9093->9093/tcp   alertmanager
33287c0939aa   prom/prometheus:v2.48.0             "/bin/prometheus --c…"   5 days ago     Up 5 days (healthy)     0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp   prometheus
c9dfbeb87ee7   prom/node-exporter:v1.7.0           "/bin/node_exporter …"   5 days ago     Up 5 days               0.0.0.0:9100->9100/tcp, [::]:9100->9100/tcp   node-exporter
4. We can access web site http://172.234.217.11:8080
5. Web site user name is admin and password is Passw0rd