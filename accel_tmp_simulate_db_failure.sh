#!/bin/bash
echo "Simulating DB Failure (Blocking port 5432)..."
# Block access to default Postgres port
sudo iptables -A OUTPUT -p tcp --dport 5432 -j REJECT
echo "DB Access Blocked."
