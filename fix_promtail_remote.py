import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
os.environ["POSTGRES_HOST"] = "localhost"

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory

# Corrected Config
PROMTAIL_CONFIG = """server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
- job_name: system
  static_configs:
  - targets:
      - localhost
    labels:
      job: varlogs
      # Correct placement of __path__
      __path__: /var/log/apache2/*.log
  
  pipeline_stages:
  - match:
      selector: '{job="varlogs"}'
      stages:
      - regex:
          expression: "^(?P<time>\\\\d{4}-\\\\d{2}-\\\\d{2} \\\\d{2}:\\\\d{2}:\\\\d{2}) (?P<message>.*)$"
      - timestamp:
          source: time
          format: "2006-01-02 15:04:05"
"""

async def main():
    server_identifier = "15.204.233.209"
    print(f"Fixing Promtail Config on: {server_identifier}")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name")
        result = await db.execute(query, {"name": server_identifier})
        server = result.fetchone()
        
        if not server:
            print("Server not found.")
            return

        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            # Write temp file locally
            local_path = "temp_promtail_config.yaml"
            with open(local_path, "w", newline='\n') as f:
                f.write(PROMTAIL_CONFIG)
            
            remote_path = "/etc/promtail/config.yaml"
            
            if hasattr(executor, 'upload_file'):
                print(f"Uploading config to {remote_path}...")
                await executor.execute(f"sudo chmod 777 /etc/promtail") # temp allow write
                await executor.upload_file(local_path, remote_path)
                await executor.execute(f"sudo chmod 644 {remote_path}")
                print("Config uploaded.")
                
                print("Restarting Promtail...")
                res = await executor.execute("sudo systemctl restart promtail")
                if res.exit_code == 0:
                    print("Restart success.")
                else:
                    print(f"Restart failed: {res.stderr}")
                    
                print("Checking status...")
                res = await executor.execute("systemctl status promtail --no-pager")
                print(res.stdout)
            else:
                print("Executor feature missing.")

if __name__ == "__main__":
    asyncio.run(main())
