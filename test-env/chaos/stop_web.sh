#!/bin/bash
# Simulates a service crash
echo "Stopping Web Target Container..."
docker stop web-target
echo "Web Target stopped. Alert should fire in ~1 minute."
