import asyncio
import sys
import os

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.services.executor_factory import ExecutorFactory
from sqlalchemy import text

CONFIG_CONTENT = """server:
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
  pipeline_stages:
  - match:
      selector: '{job="varlogs"}'
      stages:
      - regex:
          expression: "^(?P<time>\\\\d{4}-\\\\d{2}-\\\\d{2} \\\\d{2}:\\\\d{2}:\\\\d{2}) (?P<message>.*)$"
      - timestamp:
          source: time
          format: "2006-01-02 15:04:05"
  __path__ : /var/log/apache2/*.log
"""

async def main():
    server_name = "t-aiops-01"
    print(f"Updating Promtail on {server_name}...")
    
    async with AsyncSessionLocal() as db:
        query = text("SELECT * FROM server_credentials WHERE hostname = :name OR name = :name")
        result = await db.execute(query, {"name": server_name})
        server = result.fetchone()
        
        executor = ExecutorFactory.get_executor(server, None)
        
        async with executor:
            # Overwrite config
            # We can use simple echo since we don't need sudo for writing to /tmp then mv
            # But the file is in /etc/promtail/config.yaml which needs sudo.
            
            # 1. Write to tmp file locally
            with open("temp_promtail_config.yaml", "w", newline='\n') as f:
                f.write(CONFIG_CONTENT)
                
            # 2. Upload
            await executor.upload_file("temp_promtail_config.yaml", "/tmp/promtail_config.yaml")
            
            # 3. Move and Restart
            print("Applying config...")
            await executor.execute("sudo mv /tmp/promtail_config.yaml /etc/promtail/config.yaml")
            await executor.execute("sudo systemctl restart promtail")
            print("Promtail restarted.")

if __name__ == "__main__":
    asyncio.run(main())
