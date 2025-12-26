#!/bin/bash
# Send test alerts to repopulate the database
# Using Prometheus Alertmanager webhook format

WEBHOOK_URL="http://localhost:8080/webhook/alerts"

echo "Sending CPU alerts..."
for i in 1 2 3 4 5; do
  curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"HighCPUUsage","severity":"critical","instance":"web-server-'$i'","job":"node-exporter"},"annotations":{"summary":"High CPU usage on web-server-'$i'","description":"CPU usage is above 90%"},"startsAt":"2025-12-20T04:00:00Z","fingerprint":"cpu-high-'$i'"}]}'
  echo " - CPU Alert $i sent"
done

echo "Sending Memory alerts..."
for i in 1 2 3; do
  curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"HighMemoryUsage","severity":"warning","instance":"db-server-'$i'","job":"node-exporter"},"annotations":{"summary":"High memory on db-server-'$i'","description":"Memory usage above 85%"},"startsAt":"2025-12-20T04:00:00Z","fingerprint":"mem-high-'$i'"}]}'
  echo " - Memory Alert $i sent"
done

echo "Sending Disk alerts..."
for i in 1 2; do
  curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"DiskSpaceLow","severity":"warning","instance":"storage-'$i'","job":"node-exporter"},"annotations":{"summary":"Low disk space on storage-'$i'","description":"Disk usage above 80%"},"startsAt":"2025-12-20T04:00:00Z","fingerprint":"disk-low-'$i'"}]}'
  echo " - Disk Alert $i sent"
done

echo "Sending Network alerts..."
for i in 1 2 3; do
  curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"NetworkLatencyHigh","severity":"info","instance":"router-'$i'","job":"blackbox-exporter"},"annotations":{"summary":"High latency on router-'$i'","description":"Network latency above 100ms"},"startsAt":"2025-12-20T04:00:00Z","fingerprint":"net-latency-'$i'"}]}'
  echo " - Network Alert $i sent"
done

echo "Sending Service Down alerts..."
for i in 1 2; do
  curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"ServiceDown","severity":"critical","instance":"api-server-'$i'","job":"http-probe"},"annotations":{"summary":"Service down on api-server-'$i'","description":"HTTP probe failed"},"startsAt":"2025-12-20T04:00:00Z","fingerprint":"svc-down-'$i'"}]}'
  echo " - Service Down Alert $i sent"
done

echo ""
echo "Done! Total alerts sent: 15"
