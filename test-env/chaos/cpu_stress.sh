#!/bin/bash
# Simulates High CPU usage on the host for 60 seconds
echo "Triggering High CPU Load on Host..."
stress-ng --cpu 2 --timeout 60s &
echo "CPU Load started (2 cores, 60s timeout)"
