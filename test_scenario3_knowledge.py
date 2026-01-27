"""
Test Scenario 3: Knowledge Retrieval (RAG/SOP) - The "Policy Expert"

This script tests the AI's ability to retrieve and synthesize information
from the uploaded SOP document.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"

def login():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Passw0rd"}
    )
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✓ Logged in successfully")
        return token
    else:
        print(f"✗ Login failed: {response.text}")
        return None

def test_knowledge_search(token):
    """Test direct knowledge search"""
    print("\n" + "="*70)
    print("TEST 1: Direct Knowledge Search")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test different queries
    queries = [
        "Apache maintenance escalation",
        "Who do I notify for Apache restart",
        "What is the maintenance window",
        "Manual escalation policy"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        response = requests.post(
            f"{BASE_URL}/api/knowledge/search",
            headers=headers,
            json={"query": query, "doc_types": ["sop"], "limit": 3}
        )
        
        if response.status_code == 200:
            results = response.json().get("results", [])
            print(f"  Results: {len(results)}")
            for result in results:
                title = result.get('title') or result.get('document_title', 'Unknown')
                similarity = result.get('similarity', 0)
                content_preview = result.get('content', '')[:100]
                print(f"    - {title} (similarity: {similarity:.2f})")
                print(f"      Preview: {content_preview}...")
        else:
            print(f"  Error: {response.status_code} - {response.text}")

def test_ai_chat_scenario(token):
    """Test Scenario 3 questions with AI chat"""
    print("\n" + "="*70)
    print("TEST 2: AI Chat - Scenario 3 Questions")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Scenario 3 test questions
    questions = [
        "Who do I notify if I need to restart Apache?",
        "What is the maintenance window for Apache?",
        "Can I restart Apache right now?",
    ]
    
    for question in questions:
        print(f"\n{'─'*70}")
        print(f"USER: {question}")
        print(f"{'─'*70}")
        
        # Send message to troubleshoot chat
        response = requests.post(
            f"{BASE_URL}/api/troubleshoot/chat",
            headers=headers,
            json={
                "message": question,
                "mode": "inquiry"  # Use inquiry mode for knowledge retrieval
            }
        )
        
        if response.status_code != 200:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            continue
        
        result = response.json()
        
        # Show AI response
        if "response" in result:
            print(f"\nAI RESPONSE:")
            print(result["response"])
        elif "message" in result:
            print(f"\nAI RESPONSE:")
            print(result["message"])
        
        # Show tools used
        if "tools_used" in result and result["tools_used"]:
            print(f"\nTools used: {', '.join(result['tools_used'])}")
        
        print()
        time.sleep(1)  # Brief pause between questions

def check_document_status(token):
    """Check if SOP document exists and has chunks"""
    print("\n" + "="*70)
    print("CHECKING SOP Document Status")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # List all documents
    response = requests.get(
        f"{BASE_URL}/api/knowledge/documents",
        headers=headers
    )
    
    if response.status_code == 200:
        docs = response.json().get("documents", [])
        print(f"\nTotal documents: {len(docs)}")
        
        for doc in docs:
            if "Apache" in doc.get("title", ""):
                print(f"\n  ✓ Found: {doc['title']}")
                print(f"    ID: {doc['id']}")
                print(f"    Type: {doc['doc_type']}")
                print(f"    Chunks: {doc.get('chunks_count', 0)}")
                print(f"    Status: {doc.get('status', 'unknown')}")
    else:
        print(f"Error: {response.status_code}")

def main():
    print("\n" + "="*70)
    print("SCENARIO 3: Knowledge Retrieval (RAG/SOP) - The 'Policy Expert'")
    print("="*70)
    
    token = login()
    if not token:
        return
    
    # Check document status
    check_document_status(token)
    
    # Test knowledge search
    test_knowledge_search(token)
    
    # Test with AI chat
    print("\n\nStarting AI Chat tests...")
    print("Note: This may take a few minutes as the AI processes each question.\n")
    test_ai_chat_scenario(token)
    
    print("\n" + "="*70)
    print("SCENARIO 3 TESTING COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
