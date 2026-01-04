
import base64
import subprocess
import time

REQUIREMENTS_TXT = r"""# Web framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
asyncpg==0.29.0
alembic==1.13.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
cryptography==42.0.2

# LLM
litellm==1.30.1
anthropic==0.18.1
langchain==0.1.16
langchain-community==0.0.34
asyncssh==2.14.2

# Templates
jinja2==3.1.3

# Phase 2: Knowledge Base dependencies
pgvector
openai
Pillow
pypdf2
PyMuPDF==1.23.8
markdown
anthropic==0.18.1

# Utilities
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0
httpx==0.26.0
slowapi==0.1.9
prometheus_client==0.19.0
aiofiles==23.2.1
pyyaml==6.0.1
json-logic

# Scheduler
apscheduler==3.10.4
pytz==2023.3
croniter==2.0.1

# ML & Clustering (Week 1-2: Alert Clustering)
scikit-learn==1.3.2
numpy==1.24.3
scipy==1.10.1

# ITSM Integration (Week 5-6: Change Correlation)
jsonpath-ng==1.6.1
python-dateutil==2.8.2
"""

def main():
    encoded_reqs = base64.b64encode(REQUIREMENTS_TXT.encode('utf-8')).decode('utf-8')
    
    # 1. Update requirements.txt
    print("Updating requirements.txt on Lab VM...")
    cmd_update = f"echo {encoded_reqs} | base64 -d > /aiops/requirements.txt"
    subprocess.run(["ssh", "ubuntu@15.204.244.73", cmd_update])
    
    # 2. Rebuild and Restart
    print("Rebuilding remediation-engine...")
    cmd_rebuild = "cd /aiops && docker compose build remediation-engine && docker compose up -d remediation-engine"
    subprocess.run(["ssh", "ubuntu@15.204.244.73", cmd_rebuild])
    
    # 3. Wait for Health
    print("Waiting for startup (30s)...")
    time.sleep(30)
    
    # 4. SSH Key Setup (Re-run)
    print("Setting up SSH Keys...")
    cmd_keys = "docker exec remediation-engine mkdir -p /home/appuser/.ssh && " \
               "docker exec remediation-engine ssh-keygen -t rsa -N '' -f /home/appuser/.ssh/id_rsa && " \
               "docker exec remediation-engine cat /home/appuser/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys"
               
    subprocess.run(["ssh", "ubuntu@15.204.244.73", cmd_keys])
    
    print("Update Complete.")

if __name__ == "__main__":
    main()
