#!/usr/bin/env python3
"""
Phase 1 Foundation API Testing Script
Tests Application Registry, Components, and Dependencies
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def print_header(text):
    print(f"\n{'='*50}")
    print(f"{text}")
    print(f"{'='*50}\n")

def print_step(num, text):
    print(f"{num}. {text}")

def print_success(text):
    print(f"   [OK] {text}")

def print_error(text):
    print(f"   [FAIL] {text}")

def print_info(text):
    print(f"   {text}")

def main():
    print_header("Phase 1 Foundation API Testing")
    
    # 1. Login
    print_step(1, "Logging in...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "Passw0rd"}
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        print_success("Login successful")
        headers = {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print_error(f"Login failed: {e}")
        return
    
    # 2. Create Application
    print_step(2, "Creating application 'video-platform'...")
    try:
        app_data = {
            "name": "video-platform",
            "display_name": "Video Streaming Platform",
            "description": "Main video streaming application",
            "team_owner": "platform-team",
            "criticality": "critical",
            "tech_stack": {
                "backend": "Python/FastAPI",
                "frontend": "React",
                "database": "PostgreSQL"
            },
            "alert_label_matchers": {"app": "video-platform"}
        }
        response = requests.post(
            f"{BASE_URL}/api/applications",
            json=app_data,
            headers=headers
        )
        response.raise_for_status()
        app = response.json()
        app_id = app["id"]
        print_success(f"Application created: {app_id}")
    except Exception as e:
        print_error(f"Failed: {e}")
        return
    
    # 3. Create Components
    print_step(3, "Creating components...")
    
    components = [
        {
            "name": "api-server",
            "component_type": "compute",
            "description": "Main API server",
            "criticality": "high",
            "endpoints": {"host": "api.example.com", "port": 8000}
        },
        {
            "name": "postgres-db",
            "component_type": "database",
            "description": "PostgreSQL database",
            "criticality": "critical"
        },
        {
            "name": "redis-cache",
            "component_type": "cache",
            "description": "Redis cache layer",
            "criticality": "medium"
        }
    ]
    
    created_components = {}
    for comp in components:
        try:
            response = requests.post(
                f"{BASE_URL}/api/applications/{app_id}/components",
                json=comp,
                headers=headers
            )
            response.raise_for_status()
            comp_data = response.json()
            created_components[comp["name"]] = comp_data
            print_success(f"{comp['name']} component created: {comp_data['id']}")
        except Exception as e:
            print_error(f"Failed to create {comp['name']}: {e}")
    
    # 4. Create Dependencies
    print_step(4, "Creating dependencies...")
    
    dependencies = [
        {
            "from": "api-server",
            "to": "postgres-db",
            "type": "sync",
            "impact": "API cannot serve requests without database"
        },
        {
            "from": "api-server",
            "to": "redis-cache",
            "type": "optional",
            "impact": "Performance degradation, no caching"
        }
    ]
    
    for dep in dependencies:
        try:
            dep_data = {
                "from_component_id": created_components[dep["from"]]["id"],
                "to_component_id": created_components[dep["to"]]["id"],
                "dependency_type": dep["type"],
                "failure_impact": dep["impact"]
            }
            response = requests.post(
                f"{BASE_URL}/api/applications/{app_id}/dependencies",
                json=dep_data,
                headers=headers
            )
            response.raise_for_status()
            print_success(f"Dependency created: {dep['from']} -> {dep['to']}")
        except Exception as e:
            print_error(f"Failed to create dependency: {e}")
    
    # 5. Get Dependency Graph
    print_step(5, "Fetching dependency graph...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/applications/{app_id}/dependency-graph",
            headers=headers
        )
        response.raise_for_status()
        graph = response.json()
        print_success("Dependency graph retrieved")
        print_info(f"Nodes: {len(graph['nodes'])}")
        for node in graph['nodes']:
            print(f"       - {node['name']} ({node['type']})")
        print_info(f"Edges: {len(graph['edges'])}")
        for edge in graph['edges']:
            from_node = next(n for n in graph['nodes'] if n['id'] == edge['from'])
            to_node = next(n for n in graph['nodes'] if n['id'] == edge['to'])
            print(f"       - {from_node['name']} -> {to_node['name']} ({edge['type']})")
    except Exception as e:
        print_error(f"Failed: {e}")
    
    # 6. List Applications
    print_step(6, "Listing all applications...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/applications",
            headers=headers
        )
        response.raise_for_status()
        apps = response.json()
        print_success(f"Found {apps['total']} application(s)")
        for app in apps['items']:
            print(f"       - {app['display_name']} [{app['criticality']}]")
    except Exception as e:
        print_error(f"Failed: {e}")
    
    # 7. Get Application Details
    print_step(7, "Fetching application details...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/applications/{app_id}",
            headers=headers
        )
        response.raise_for_status()
        app_detail = response.json()
        print_success(f"Application: {app_detail['display_name']}")
        print_info(f"Components: {len(app_detail['components'])}")
        for comp in app_detail['components']:
            print(f"       - {comp['name']} [{comp['component_type']}]")
    except Exception as e:
        print_error(f"Failed: {e}")
    
    print_header("Phase 1 Testing Complete")
    print("Summary:")
    print(f"  Application ID: {app_id}")
    print(f"  Swagger UI: http://localhost:8080/docs")
    print(f"  Dashboard: http://localhost:8080")
    print()

if __name__ == "__main__":
    main()
