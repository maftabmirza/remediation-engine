#!/usr/bin/env python3
"""
Test Script for Scenario 4: DB Connection Failure Demo
This script helps verify and execute the DB failure scenario for demo purposes.
"""

import subprocess
import requests
import time
import sys
from datetime import datetime

# Configuration
SERVER_HOST = "15.204.233.209"
WEBSITE_URL = f"http://{SERVER_HOST}/index.php"
SSH_USER = "ubuntu"
SSH_HOST = f"{SSH_USER}@{SERVER_HOST}"
DB_PORT = "3306"  # MySQL default, change to 5432 for PostgreSQL

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(step_num, description):
    """Print a formatted step header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Step {step_num}: {description} ==={Colors.END}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_warning(message):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def run_ssh_command(command, description):
    """Execute SSH command on remote server"""
    print(f"  Running: {description}")
    # Use list format for subprocess to avoid shell quoting issues
    try:
        result = subprocess.run(
            ["ssh", SSH_HOST, command],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print_success(description)
            if result.stdout.strip():
                print(f"    Output: {result.stdout.strip()}")
            return True, result.stdout
        else:
            print_error(f"{description} failed")
            if result.stderr.strip():
                print(f"    Error: {result.stderr.strip()}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"{description} timed out")
        return False, "Timeout"
    except Exception as e:
        print_error(f"{description} failed: {str(e)}")
        return False, str(e)

def check_website_status():
    """Check if website is responding"""
    try:
        response = requests.get(WEBSITE_URL, timeout=10)
        if response.status_code == 200:
            print_success(f"Website is UP (Status: {response.status_code})")
            return True, response.status_code
        else:
            print_warning(f"Website returned status: {response.status_code}")
            return False, response.status_code
    except requests.exceptions.RequestException as e:
        print_error(f"Website is DOWN: {str(e)}")
        return False, str(e)

def verify_prerequisites():
    """Verify all prerequisites are met"""
    print_step(1, "Verifying Prerequisites")
    
    # Check SSH connectivity
    success, _ = run_ssh_command("echo 'SSH connected'", "SSH connectivity")
    if not success:
        print_error("Cannot connect to server via SSH. Check your SSH keys.")
        return False
    
    # Check website baseline
    print(f"\n  Checking website: {WEBSITE_URL}")
    is_up, _ = check_website_status()
    if not is_up:
        print_warning("Website is not responding. This may be expected if already in failure state.")
    
    # Check if Apache is running
    success, output = run_ssh_command(
        "systemctl is-active apache2",
        "Apache service status"
    )
    
    # Check database service
    run_ssh_command(
        "systemctl is-active mysql || systemctl is-active mariadb || systemctl is-active postgresql || echo 'No DB service detected'",
        "Database service status"
    )
    
    return True

def deploy_scripts():
    """Deploy simulation scripts to remote server"""
    print_step(2, "Deploying Scripts to Server")
    
    scripts = [
        "accel_tmp_simulate_db_failure.sh",
        "accel_tmp_restore_db_access.sh"
    ]
    
    for script in scripts:
        print(f"  Copying {script}...")
        try:
            result = subprocess.run(
                ["scp", script, f"{SSH_HOST}:~/"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print_success(f"{script} deployed")
            else:
                print_error(f"Failed to copy {script}")
                print(f"    Error: {result.stderr.strip()}")
                return False
        except Exception as e:
            print_error(f"Failed to copy {script}: {str(e)}")
            return False
    
    # Make scripts executable
    success, _ = run_ssh_command(
        "chmod +x ~/accel_tmp_simulate_db_failure.sh ~/accel_tmp_restore_db_access.sh",
        "Make scripts executable"
    )
    
    return success

def simulate_failure():
    """Execute the DB failure simulation"""
    print_step(3, "Simulating Database Failure")
    
    # Execute uploaded script
    success, output = run_ssh_command(
        f"~/accel_tmp_simulate_db_failure.sh {DB_PORT}",
        "Execute failure simulation script"
    )
    
    if not success:
        print_warning("Script execution failed. Trying direct iptables command...")
        # Execute inline
        success, output = run_ssh_command(
            f"sudo iptables -A OUTPUT -p tcp --dport {DB_PORT} -j DROP",
            f"Block database port {DB_PORT}"
        )
    
    print("\n  Waiting 5 seconds for failure to take effect...")
    time.sleep(5)
    
    print(f"\n  Verifying failure is active:")
    check_website_status()
    
    # Check error logs
    print("\n  Checking error logs for database connection errors:")
    run_ssh_command(
        "sudo tail -20 /var/log/apache2/error.log | grep -i 'connection\\|database\\|mysql\\|pdo' || echo 'No DB errors found in logs yet'",
        "Search error logs"
    )

def verify_failure():
    """Verify the failure is properly simulated"""
    print_step(4, "Verifying Failure State")
    
    # Apache should still be running
    success, output = run_ssh_command(
        "systemctl is-active apache2",
        "Apache service (should be running)"
    )
    
    # Website should return error
    print(f"\n  Testing website: {WEBSITE_URL}")
    is_up, status = check_website_status()
    
    if is_up:
        print_warning("Website is still responding normally. Failure may not be active.")
    else:
        print_success("Website is returning errors as expected")
    
    # Database service status
    run_ssh_command(
        "systemctl status mysql 2>/dev/null | grep Active || systemctl status postgresql 2>/dev/null | grep Active || echo 'DB service check'",
        "Database service status check"
    )

def ai_prompt_guidance():
    """Provide guidance for testing with AI"""
    print_step(5, "AI Testing Guidance")
    
    print(f"\n{Colors.BOLD}Now test the AI troubleshooting:{Colors.END}")
    print(f"\n1. Navigate to: {Colors.BLUE}http://localhost:8080/ai{Colors.END} or {Colors.BLUE}http://localhost:8080/troubleshoot{Colors.END}")
    print(f"\n2. Enter this prompt:")
    print(f"   {Colors.YELLOW}\"The application at http://{SERVER_HOST}/index.php is broken, please help\"{Colors.END}")
    print(f"\n3. Expected AI behavior:")
    print(f"   - AI checks Apache status (should be running)")
    print(f"   - AI reads error logs (should find database errors)")
    print(f"   - AI identifies: 'Apache is running but cannot connect to database'")
    print(f"   - AI suggests running database connectivity diagnostics")
    print(f"   - AI recommends checking database service or network")
    print(f"\n4. When ready to restore, press ENTER...")
    
    input()

def restore_system():
    """Restore the system to normal operation"""
    print_step(6, "Restoring System")
    
    # Execute uploaded script
    success, output = run_ssh_command(
        f"~/accel_tmp_restore_db_access.sh {DB_PORT}",
        "Execute restoration script"
    )
    
    if not success:
        print_warning("Script execution failed. Trying direct commands...")
        # Execute inline restoration
        run_ssh_command(
            f"sudo iptables -D OUTPUT -p tcp --dport {DB_PORT} -j DROP",
            f"Remove iptables block on port {DB_PORT}"
        )
        run_ssh_command(
            "sudo systemctl start mysql || sudo systemctl start mariadb || sudo systemctl start postgresql",
            "Start database services"
        )
    
    print("\n  Waiting 5 seconds for system to stabilize...")
    time.sleep(5)
    
    print(f"\n  Verifying restoration:")
    check_website_status()

def main():
    """Main test execution"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("  Scenario 4: DB Connection Failure - Demo Test Script")
    print("  Target: http://{}/index.php".format(SERVER_HOST))
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    print(f"{Colors.YELLOW}This script will:{Colors.END}")
    print("  1. Verify prerequisites (SSH, website, services)")
    print("  2. Simulate database connection failure")
    print("  3. Verify the failure is active")
    print("  4. Guide you through AI testing")
    print("  5. Restore the system")
    print(f"\n{Colors.YELLOW}Press ENTER to continue or Ctrl+C to cancel...{Colors.END}")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    
    # Execute test steps
    if not verify_prerequisites():
        print_error("\nPrerequisites check failed. Cannot proceed.")
        sys.exit(1)
    
    simulate_failure()
    verify_failure()
    ai_prompt_guidance()
    restore_system()
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}")
    if not deploy_scripts():
        print_error("\nFailed to deploy scripts. Cannot proceed.")
        sys.exit(1)
    
    print("=" * 70)
    print("  ✅ Scenario 4 Test Complete!")
    print("=" * 70)
    print(f"{Colors.END}\n")
    
    print("Next steps:")
    print("  - Review the AI's response quality")
    print("  - Check if AI correctly identified the database issue")
    print("  - Verify website is fully restored")
    print("  - Document any improvements needed for the demo")

if __name__ == "__main__":
    main()
