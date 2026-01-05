---
trigger: always_on
---

Local development environment 

We can test code local and deploy container on laptop, docker desktop is already installed
1. local code PS D:\remediate-engine-antigravity\remediation-engine>
2. Local windows container 
72cb309609e6   remediate-engine-antigravity-remediation-engine   "./entrypoint.sh"        12 hours ago   Up 11 hours (unhealthy)   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp                                                                                                                 remediation-engine
7b8f8bc97126   grafana/grafana-enterprise:latest                 "/run.sh"                3 days ago     Up 2 days                 3000/tcp                                                                                                                                                    aiops-grafana
dbad902c567e   aiops-testing-app-aiops-testmgr-app               "uvicorn app.main:ap…"   4 days ago     Up 2 days (healthy)       0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp                                                                                                               aiops-testmgr-app
a6653726384f   postgres:16                                       "docker-entrypoint.s…"   4 days ago     Up 2 days (healthy)       0.0.0.0:55433->5432/tcp, [::]:55433->5432/tcp                                                                                                               aiops-testmgr-db
9aa325ebac4f   grafana/loki:latest                               "/usr/bin/loki -conf…"   12 days ago    Up 2 days                 0.0.0.0:3100->3100/tcp, [::]:3100->3100/tcp                                                                                                                 aiops-loki
bc68dc005384   prom/prometheus:latest                            "/bin/prometheus --c…"   12 days ago    Up 2 days                 0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp                                                                                                                 aiops-prometheus
668b13c8d6dc   prom/alertmanager:latest                          "/bin/alertmanager -…"   12 days ago    Up 2 days                 0.0.0.0:9093->9093/tcp, [::]:9093->9093/tcp                                                                                                                 aiops-alertmanager
e5487f2b5005   grafana/mimir:latest                              "/bin/mimir -config.…"   12 days ago    Up 2 days                 0.0.0.0:9009->9009/tcp, [::]:9009->9009/tcp                                                                                                                 aiops-mimir
13089dd2927b   grafana/tempo:latest                              "/tempo -config.file…"   12 days ago    Up 2 days                 0.0.0.0:3200->3200/tcp, [::]:3200->3200/tcp, 0.0.0.0:4317-4318->4317-4318/tcp, [::]:4317-4318->4317-4318/tcp, 0.0.0.0:9411->9411/tcp, [::]:9411->9411/tcp   aiops-tempo
788239e07834   pgvector/pgvector:pg16                            "docker-entrypoint.s…"   2 weeks ago    Up 2 days (healthy)       0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp                                                                                                                 aiops-postgres

Important : We need to change code on local lapotop first, test , push to git and connect to 172.234.217.11 and pull, docker compose/restart and test 

