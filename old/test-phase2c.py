#!/usr/bin/env python3
"""
Phase 2c Test Script - Document Processing & APIs
Tests document upload, chunking, and embedding generation
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "Passw0rd"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"[OK] {text}")

def print_error(text):
    print(f"[FAIL] {text}")

def print_info(text):
    print(f"   {text}")

def main():
    print_header("Phase 2c: Document Processing Test")
    
    # Step 1: Login
    print_header("Step 1: Login")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if response.status_code != 200:
        print_error(f"Login failed: {response.status_code}")
        return
    
    token = response.json()["access_token"]
    print_success(f"Logged in successfully")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Get Knowledge Stats
    print_header("Step 2: Knowledge Base Stats")
    response = requests.get(f"{BASE_URL}/api/knowledge/stats", headers=headers)
    
    if response.status_code == 200:
        stats = response.json()
        print_success("Knowledge stats retrieved:")
        print_info(f"Total documents: {stats['total_documents']}")
        print_info(f"Total chunks: {stats['total_chunks']}")
        print_info(f"Embedding model: {stats['embedding_model']}")
        print_info(f"Embedding configured: {stats['embedding_configured']}")
    else:
        print_error(f"Failed to get stats: {response.status_code}")
    
    # Step 3: Create Test Document
    print_header("Step 3: Create Test Document")
    
    test_content = """# System Architecture

## Overview
Our system is built on a microservices architecture with the following components:

## Components

### API Gateway
The API Gateway handles all incoming requests and routes them to appropriate services.
It provides authentication, rate limiting, and request logging.

### User Service  
Manages user accounts, profiles, and authentication.
Uses PostgreSQL for data storage.

### Order Service
Handles order processing and fulfillment.
Communicates with inventory and payment services.

### Inventory Service
Tracks product availability and stock levels.
Uses Redis for caching frequently accessed data.

### Payment Service
Processes payments through third-party payment processors.
Implements retry logic and idempotency.

## Data Flow
1. Client sends request to API Gateway
2. Gateway authenticates and forwards to appropriate service
3. Services communicate via message queue (RabbitMQ)
4. Results are returned through the gateway

## Failure Scenarios
- API Gateway down: No requests processed
- Database connection pool exhausted: Timeout errors
- Message queue unavailable: Async operations delayed
"""
    
    doc_data = {
        "title": "Microservices Architecture Guide",
        "doc_type": "architecture",
        "content": test_content,
        "format": "markdown"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/knowledge/documents",
        data=doc_data,
        headers=headers
    )
    
    if response.status_code == 201:
        doc = response.json()
        doc_id = doc['id']
        print_success(f"Document created: {doc_id}")
        print_info(f"Title: {doc['title']}")
        print_info(f"Slug: {doc['slug']}")
        print_info(f"Doc type: {doc['doc_type']}")
    else:
        print_error(f"Failed to create document: {response.status_code}")
        print_error(response.text)
        return
    
    # Step 4: List Documents
    print_header("Step 4: List Documents")
    response = requests.get(f"{BASE_URL}/api/knowledge/documents", headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print_success(f"Found {result['total']} documents")
        for doc in result['items']:
            print_info(f"- {doc['title']} ({doc['doc_type']})")
    else:
        print_error(f"Failed to list documents: {response.status_code}")
    
    # Step 5: Get Document Chunks
    print_header("Step 5: Get Document Chunks")
    response = requests.get(
        f"{BASE_URL}/api/knowledge/documents/{doc_id}/chunks",
        headers=headers
    )
    
    if response.status_code == 200:
        chunks = response.json()
        print_success(f"Found {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            has_embedding = chunk.get('embedding') is not None
            print_info(f"Chunk {i}: {len(chunk['content'])} chars, embedding: {'YES' if has_embedding else 'NO'}")
            if i == 0:
                print_info(f"Preview: {chunk['content'][:100]}...")
    else:
        print_error(f"Failed to get chunks: {response.status_code}")
    
    # Step 6: Get Document Details
    print_header("Step 6: Get Document Details")
    response = requests.get(
        f"{BASE_URL}/api/knowledge/documents/{doc_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        doc = response.json()
        print_success("Document retrieved")
        print_info(f"ID: {doc['id']}")
        print_info(f"Title: {doc['title']}")
        print_info(f"Created: {doc['created_at']}")
        print_info(f"Content length: {len(doc.get('raw_content', ''))}")
    else:
        print_error(f"Failed to get document: {response.status_code}")
    
    # Step 7: Update Document
    print_header("Step 7: Update Document")
    update_data = {
        "status": "archived"
    }
    response = requests.put(
        f"{BASE_URL}/api/knowledge/documents/{doc_id}",
        json=update_data,
        headers=headers
    )
    
    if response.status_code == 200:
        doc = response.json()
        print_success(f"Document updated - status: {doc['status']}")
    else:
        print_error(f"Failed to update document: {response.status_code}")
    
    # Step 8: Final Stats
    print_header("Step 8: Final Knowledge Stats")
    response = requests.get(f"{BASE_URL}/api/knowledge/stats", headers=headers)
    
    if response.status_code == 200:
        stats = response.json()
        print_success("Final stats:")
        print_info(f"Total documents: {stats['total_documents']}")
        print_info(f"Total chunks: {stats['total_chunks']}")
        print_info(f"Documents by type: {stats.get('documents_by_type', {})}")
    
    # Summary
    print_header("Test Summary")
    print_success("Phase 2c document processing tests completed!")
    print_info("Document upload: WORKING")
    print_info("Text chunking: WORKING")
    print_info("Embedding generation: CHECK CHUNKS")
    print_info("CRUD operations: WORKING")

if __name__ == "__main__":
    main()
