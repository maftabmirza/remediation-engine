import socket
import sys

host = "grafana"
port = 3000

print(f"Testing connectivity to {host}:{port}...")

try:
    ip = socket.gethostbyname(host)
    print(f"Resolved {host} to {ip}")
except Exception as e:
    print(f"DNS Resolution failed: {e}")
    sys.exit(1)

try:
    s = socket.create_connection((host, port), timeout=5)
    print("Connection successful!")
    s.close()
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
