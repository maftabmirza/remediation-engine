import socket
import sys

hosts_to_check = ["grafana", "aiops-grafana", "aiops-prometheus", "prometheus"]
port = 3000

for host in hosts_to_check:
    print(f"Testing DNS for {host}...")
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ Resolved {host} to {ip}")
    except Exception as e:
        print(f"❌ DNS Resolution failed for {host}: {e}")
