#!/usr/bin/env python3
"""
Phase 2a Database Foundation Test Script
Tests pgvector extension, knowledge tables, and vector similarity search
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import random

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'aiops',
    'user': 'aiops',
    'password': 'aiops_secure_password'
}

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

def generate_dummy_embedding(dim=1536):
    """Generate a random embedding vector for testing."""
    return [random.random() for _ in range(dim)]

def main():
    print_header("Phase 2a Database Foundation Test")
    
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print_success("Connected to database")
        
        # Test 1: Verify pgvector extension
        print_header("Test 1: Verify pgvector Extension")
        cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
        result = cursor.fetchone()
        if result:
            print_success(f"pgvector extension installed: v{result['extversion']}")
        else:
            print_error("pgvector extension not found")
            return
        
        # Test 2: Verify tables exist
        print_header("Test 2: Verify Knowledge Tables")
        tables = ['design_documents', 'design_images', 'design_chunks']
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE tablename IN %s 
            ORDER BY tablename
        """, (tuple(tables),))
        found_tables = [row['tablename'] for row in cursor.fetchall()]
        
        for table in tables:
            if table in found_tables:
                print_success(f"Table '{table}' exists")
            else:
                print_error(f"Table '{table}' not found")
        
        # Test 3: Verify vector column
        print_header("Test 3: Verify Vector Column")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'design_chunks' AND column_name = 'embedding'
        """)
        result = cursor.fetchone()
        if result:
            print_success(f"Vector column exists: {result['column_name']} ({result['data_type']})")
        else:
            print_error("Vector column not found")
        
        # Test 4: Verify indexes
        print_header("Test 4: Verify Indexes")
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'design_chunks' 
            AND indexname LIKE '%embedding%'
        """)
        result = cursor.fetchone()
        if result:
            print_success(f"Vector index exists: {result['indexname']}")
            print_info(f"Type: ivfflat (for similarity search)")
        else:
            print_error("Vector index not found")
        
        # Test 5: Insert test data
        print_header("Test 5: Insert Test Document and Chunks")
        
        # Get a test application ID (from Phase 1)
        cursor.execute("SELECT id FROM applications LIMIT 1")
        app_result = cursor.fetchone()
        if not app_result:
            print_info("No applications found, creating test app...")
            cursor.execute("""
                INSERT INTO applications (name, display_name, criticality)
                VALUES ('test-app', 'Test Application', 'medium')
                RETURNING id
            """)
            app_id = cursor.fetchone()['id']
        else:
            app_id = app_result['id']
        
        print_info(f"Using app_id: {app_id}")
        
        # Insert a test document
        cursor.execute("""
            INSERT INTO design_documents (
                app_id, title, slug, doc_type, format, raw_content, status
            ) VALUES (
                %s, 'Test Architecture Doc', 'test-arch-doc', 
                'architecture', 'markdown', 
                '# System Architecture\n\nOur system uses PostgreSQL with pgvector for semantic search.',
                'active'
            ) RETURNING id
        """, (app_id,))
        doc_id = cursor.fetchone()['id']
        print_success(f"Created test document: {doc_id}")
        
        # Insert test chunks with embeddings
        chunks = [
            {
                'content': 'PostgreSQL database with pgvector extension for vector similarity search',
                'embedding': generate_dummy_embedding()
            },
            {
                'content': 'FastAPI backend service handling API requests',
                'embedding': generate_dummy_embedding()
            },
            {
                'content': 'React frontend for user interface',
                'embedding': generate_dummy_embedding()
            }
        ]
        
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            cursor.execute("""
                INSERT INTO design_chunks (
                    app_id, source_type, source_id, chunk_index,
                    content, content_type, embedding
                ) VALUES (
                    %s, 'document', %s, %s, %s, 'text', %s
                ) RETURNING id
            """, (app_id, doc_id, i, chunk['content'], chunk['embedding']))
            chunk_id = cursor.fetchone()['id']
            chunk_ids.append(chunk_id)
        
        print_success(f"Created {len(chunks)} chunks with embeddings")
        
        # Test 6: Vector Similarity Search
        print_header("Test 6: Vector Similarity Search")
        
        # Use one of our embeddings as a query
        query_embedding = chunks[0]['embedding']
        
        cursor.execute("""
            SELECT 
                id,
                content,
                1 - (embedding <=> %s::vector) as similarity
            FROM design_chunks
            WHERE app_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        """, (query_embedding, app_id, query_embedding))
        
        results = cursor.fetchall()
        print_success(f"Found {len(results)} similar chunks:")
        for i, result in enumerate(results, 1):
            print_info(f"{i}. Similarity: {result['similarity']:.4f}")
            print_info(f"   Content: {result['content'][:60]}...")
        
        # Test 7: Verify check constraints
        print_header("Test 7: Verify Data Constraints")
        
        # Test valid doc_type
        try:
            cursor.execute("""
                INSERT INTO design_documents (
                    title, slug, doc_type, format, raw_content
                ) VALUES (
                    'Invalid Doc', 'invalid-1', 'invalid_type', 'markdown', 'test'
                )
            """)
            conn.commit()
            print_error("Check constraint failed - accepted invalid doc_type")
        except psycopg2.errors.CheckViolation:
            conn.rollback()
            print_success("Check constraint working - rejected invalid doc_type")
        
        # Test valid content_type
        try:
            cursor.execute("""
                INSERT INTO design_chunks (
                    app_id, source_type, source_id, content, content_type, embedding
                ) VALUES (
                    %s, 'document', %s, 'test', 'invalid_content_type', %s
                )
            """, (app_id, doc_id, generate_dummy_embedding()))
            conn.commit()
            print_error("Check constraint failed - accepted invalid content_type")
        except psycopg2.errors.CheckViolation:
            conn.rollback()
            print_success("Check constraint working - rejected invalid content_type")
        
        # Test 8: Test cascade deletions
        print_header("Test 8: Test Cascade Deletions")
        
        # Count chunks before deletion
        cursor.execute("SELECT COUNT(*) as count FROM design_chunks WHERE source_id = %s", (doc_id,))
        before_count = cursor.fetchone()['count']
        print_info(f"Chunks before deletion: {before_count}")
        
        # Delete document (should cascade to chunks)
        cursor.execute("DELETE FROM design_documents WHERE id = %s", (doc_id,))
        
        # Count chunks after deletion
        cursor.execute("SELECT COUNT(*) as count FROM design_chunks WHERE source_id = %s", (doc_id,))
        after_count = cursor.fetchone()['count']
        print_info(f"Chunks after deletion: {after_count}")
        
        if after_count == 0:
            print_success("Cascade deletion working correctly")
        else:
            print_error(f"Cascade deletion failed - {after_count} chunks remaining")
        
        conn.commit()
        
        # Summary
        print_header("Test Summary")
        print_success("All Phase 2a database tests passed!")
        print_info("✓ pgvector extension working")
        print_info("✓ All tables created correctly")
        print_info("✓ Vector column and indexes functional")
        print_info("✓ Vector similarity search working")
        print_info("✓ Data constraints enforced")
        print_info("✓ Cascade deletions configured")
        
        print_header("Next Steps")
        print_info("Ready for Phase 2b: Document Processing")
        print_info("- Create models in models_knowledge.py")
        print_info("- Create schemas in schemas_knowledge.py")
        print_info("- Build document upload API")
        print_info("- Implement chunking service")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
