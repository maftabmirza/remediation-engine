#!/bin/bash
# Test script to create alerts for clustering

echo "Creating 10 identical alerts for clustering test..."

for i in {1..10}; do
  curl -s -X POST http://localhost:8080/webhook/alerts \
    -H 'Content-Type: application/json' \
    -d "{
      \"status\": \"firing\",
      \"alerts\": [{
        \"labels\": {
          \"alertname\": \"HighCPUUsage\",
          \"instance\": \"server-1\",
          \"job\": \"node-exporter\",
          \"severity\": \"critical\"
        },
        \"annotations\": {
          \"summary\": \"CPU usage above 90%\",
          \"description\": \"Server server-1 CPU usage is critically high\"
        },
        \"status\": \"firing\",
        \"startsAt\": \"2025-12-19T04:26:00Z\",
        \"fingerprint\": \"cpu-server-1-$i\"
      }]
    }"
  echo " - Alert $i created"
  sleep 0.2
done

echo ""
echo "✓ Created 10 identical alerts (should cluster together)"
echo ""
echo "Wait 5 minutes for clustering job or check now:"
echo "  curl http://172.234.217.11:8080/api/clusters/stats/overview"
