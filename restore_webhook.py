
import base64
import subprocess
import time



# Read webhook.py
with open(r"d:\remediate-engine-antigravity\app\routers\webhook.py", "rb") as f:
    webhook_content = base64.b64encode(f.read())  # Keep as bytes

# Read trigger_matcher.py
with open(r"d:\remediate-engine-antigravity\app\services\trigger_matcher.py", "rb") as f:
    matcher_content = base64.b64encode(f.read())  # Keep as bytes

def main():
    print("Restoring files on Lab VM...")
    
    # Restore webhook.py
    print("Uploading webhook.py...")
    subprocess.run(
        ["ssh", "ubuntu@15.204.244.73", "cat > /aiops/webhook.b64"],
        input=webhook_content,
        check=True
    )
    subprocess.run(
        ["ssh", "ubuntu@15.204.244.73", "base64 -d /aiops/webhook.b64 > /aiops/app/routers/webhook.py"],
        check=True
    )
    
    # Restore trigger_matcher.py
    print("Uploading trigger_matcher.py...")
    subprocess.run(
        ["ssh", "ubuntu@15.204.244.73", "cat > /aiops/matcher.b64"],
        input=matcher_content,
        check=True
    )
    subprocess.run(
        ["ssh", "ubuntu@15.204.244.73", "base64 -d /aiops/matcher.b64 > /aiops/app/services/trigger_matcher.py"],
        check=True
    )
    
    print("Restarting remediation-engine...")
    subprocess.run(["ssh", "ubuntu@15.204.244.73", "cd /aiops && docker compose restart remediation-engine"], check=True)
    
    print("Waiting for startup (20s)...")
    time.sleep(20)
    print("Done.")

if __name__ == "__main__":
    main()
