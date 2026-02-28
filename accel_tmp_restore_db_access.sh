#!/bin/bash
echo "Restoring DB Access..."
sudo iptables -D OUTPUT -p tcp --dport 5432 -j REJECT
echo "DB Access Restored."
