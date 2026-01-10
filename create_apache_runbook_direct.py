"""
Direct database script to create Apache restart runbook for t-aiops-01
This bypasses the API and creates the runbook directly in the database.
"""
from app.database import SessionLocal
from app.models_remediation import Runbook, RunbookStep, RunbookTrigger
from sqlalchemy.exc import IntegrityError
import json

def create_apache_restart_runbook():
    db = SessionLocal()
    try:
        # Check if runbook already exists
        existing = db.query(Runbook).filter(Runbook.name == "Restart Apache on t-aiops-01").first()
        if existing:
            print(f"✗ Runbook already exists with ID: {existing.id}")
            print("  Delete it first or use a different name.")
            return
        
        # Create the runbook
        runbook = Runbook(
            name="Restart Apache on t-aiops-01",
            description="Restarts the Apache web server on t-aiops-01 (15.204.233.209). Use this runbook when Apache is unresponsive, experiencing high load, or after configuration changes. This runbook checks the Apache status, attempts a graceful restart, and verifies the service is running.",
            category="application",
            tags=["apache", "webserver", "t-aiops-01", "restart", "service-recovery", "http", "httpd"],
            enabled=True,
            auto_execute=False,
            approval_required=True,
            created_by="admin",
            version=1
        )
        
        db.add(runbook)
        db.flush()  # Get the runbook ID
        
        print(f"✓ Created runbook: {runbook.name} (ID: {runbook.id})")
        
        # Create steps
        steps = [
            {
                "step_order": 1,
                "name": "Check Apache Status",
                "description": "Check current Apache service status before restart",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl status apache2 || sudo systemctl status httpd",
                "output_variable": "apache_status_before",
                "timeout_seconds": 30
            },
            {
                "step_order": 2,
                "name": "Stop Apache Service",
                "description": "Stop Apache service gracefully",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl stop apache2 2>/dev/null || sudo systemctl stop httpd",
                "output_variable": "apache_stop_output",
                "timeout_seconds": 60
            },
            {
                "step_order": 3,
                "name": "Wait for Cleanup",
                "description": "Wait for Apache to fully stop and release resources",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sleep 5",
                "timeout_seconds": 10
            },
            {
                "step_order": 4,
                "name": "Start Apache Service",
                "description": "Start Apache service",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl start apache2 2>/dev/null || sudo systemctl start httpd",
                "output_variable": "apache_start_output",
                "timeout_seconds": 60
            },
            {
                "step_order": 5,
                "name": "Verify Apache is Running",
                "description": "Verify that Apache service is running and active",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl is-active apache2 || sudo systemctl is-active httpd",
                "output_variable": "apache_verify",
                "expected_output": "active",
                "timeout_seconds": 30
            },
            {
                "step_order": 6,
                "name": "Check Apache Ports",
                "description": "Verify Apache is listening on expected ports (80, 443)",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo netstat -tlnp | grep -E ':(80|443) ' || sudo ss -tlnp | grep -E ':(80|443) '",
                "output_variable": "apache_ports",
                "timeout_seconds": 30
            },
            {
                "step_order": 7,
                "name": "Get Apache Status After Restart",
                "description": "Get detailed Apache status after restart",
                "step_type": "command",
                "target_os": "linux",
                "target_host": "15.204.233.209",
                "target_username": "ubuntu",
                "command_linux": "sudo systemctl status apache2 || sudo systemctl status httpd",
                "output_variable": "apache_status_after",
                "timeout_seconds": 30
            }
        ]
        
        for step_data in steps:
            step = RunbookStep(
                runbook_id=runbook.id,
                **step_data
            )
            db.add(step)
        
        print(f"✓ Created {len(steps)} steps")
        
        # Create triggers
        triggers = [
            {
                "trigger_type": "alert",
                "alert_name": "Apache Down",
                "priority": 3
            },
            {
                "trigger_type": "alert",
                "alert_name": "High HTTP Response Time",
                "priority": 2
            },
            {
                "trigger_type": "alert",
                "alert_name": "Apache High Memory",
                "priority": 2
            }
        ]
        
        for trigger_data in triggers:
            trigger = RunbookTrigger(
                runbook_id=runbook.id,
                **trigger_data
            )
            db.add(trigger)
        
        print(f"✓ Created {len(triggers)} triggers")
        
        db.commit()
        
        print(f"\n{'='*60}")
        print(f"✓ SUCCESS! Apache restart runbook created")
        print(f"{'='*60}")
        print(f"Runbook ID: {runbook.id}")
        print(f"Name: {runbook.name}")
        print(f"Category: {runbook.category}")
        print(f"Tags: {', '.join(runbook.tags)}")
        print(f"Steps: {len(steps)}")
        print(f"Triggers: {len(triggers)}")
        print(f"\nView at: http://localhost:8080/runbooks")
        print(f"\nSearchable by AI troubleshoot tool using keywords:")
        print(f"  apache, webserver, restart, t-aiops-01, service-recovery, http, httpd")
        
    except IntegrityError as e:
        db.rollback()
        print(f"✗ Database error (likely duplicate): {e}")
    except Exception as e:
        db.rollback()
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_apache_restart_runbook()
