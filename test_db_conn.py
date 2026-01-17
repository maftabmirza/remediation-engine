import psycopg2
import sys

creds = [
    ("localhost", "aiops", "aiops", "aiops"),
    ("localhost", "aiops", "aiops", "Passw0rd"),
    ("localhost", "aiops", "aiops", "admin"),
    ("localhost", "aiops", "postgres", "postgres"),
    ("172.234.217.11", "aiops", "aiops", "aiops"),
    ("172.234.217.11", "aiops", "aiops", "Passw0rd"),
]

for host, db, user, password in creds:
    print(f"Testing {user}@{host}/{db} with pass {password}...")
    try:
        conn = psycopg2.connect(
            host=host,
            database=db,
            user=user,
            password=password,
            connect_timeout=3
        )
        print(f"SUCCESS! Connected to {host}")
        conn.close()
        sys.exit(0)
    except Exception as e:
        print(f"Failed: {e}")
