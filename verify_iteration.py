import requests
import time
import uuid
import sys

BASE_URL = "http://localhost:8000"
SESSION_ID = str(uuid.uuid4())

def check_health():
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"Health check: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Server not reachable: {e}")
        return False

def create_pool():
    print("Creating pool...")
    resp = requests.post(f"{BASE_URL}/api/agents/pools", json={
        "session_id": SESSION_ID,
        "name": "Verification Pool",
        "max_concurrent": 3
    })
    print(f"Create pool: {resp.status_code}, {resp.json()}")
    return resp.json().get("id")

def spawn_agent(pool_id):
    print("Spawning agent...")
    goal = "Check execute failing command 'ls /nonexistent'"
    resp = requests.post(f"{BASE_URL}/api/agents/spawn", json={
        "pool_id": pool_id,
        "goal": goal,
        "agent_type": "background",
        "priority": 10,
        "auto_iterate": True,
        "max_iterations": 5
    })
    print(f"Spawn agent: {resp.status_code}, {resp.json()}")
    return resp.json().get("task_id")

def monitor_task(task_id):
    print(f"Monitoring task {task_id}...")
    
    last_iter = -1
    for i in range(30): # Wait up to 30 seconds
        resp = requests.get(f"{BASE_URL}/api/agents/hq/{SESSION_ID}")
        data = resp.json()
        
        # Find task
        tasks = data['tasks']['active'] + data['tasks']['queued'] + data['tasks']['completed']
        task = next((t for t in tasks if t['id'] == task_id), None)
        
        if not task:
            print("Task not found in HQ response")
            continue
            
        iter_count = task.get('iteration_count', 0)
        status = task.get('status')
        
        print(f"Time {i}s: Status={status}, Iterations={iter_count}")
        
        if iter_count > last_iter:
            print(f"-> Iteration increased to {iter_count}")
            last_iter = iter_count
            
        if iter_count >= 2:
            print("SUCCESS: Agent is iterating!")
            return True
            
        if status in ['completed', 'failed'] and iter_count == 0:
            print("Task finished without iterating?")
        
        if status == 'failed' and iter_count > 0:
             print("SUCCESS: Agent failed after iterations (expected behavior for unfixable error)")
             return True

        time.sleep(1)
        
    print("TIMEOUT: Agent did not iterate significantly")
    return False

if __name__ == "__main__":
    if not check_health():
        print("Server not running. Exiting.")
        sys.exit(1)
        
    pool_id = create_pool()
    task_id = spawn_agent(pool_id)
    success = monitor_task(task_id)
    
    if success:
        print("VERIFICATION PASSED")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED")
        sys.exit(1)
