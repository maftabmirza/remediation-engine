#!/usr/bin/env python3
"""Reset admin password and test login"""
import os
import sys
sys.path.insert(0, '/app')
import requests

from passlib.context import CryptContext
from sqlalchemy import create_engine, text

# Hash the password
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
password_hash = pwd_context.hash('Passw0rd')

# Connect to database
db_url = os.environ.get('DATABASE_URL', 'postgresql://aiops:aiops_secure_password@postgres:5432/aiops')
engine = create_engine(db_url)

# Update admin password
with engine.connect() as conn:
    result = conn.execute(
        text('UPDATE users SET password_hash = :hash WHERE username = :username'),
        {'hash': password_hash, 'username': 'admin'}
    )
    conn.commit()
    print(f'✅ Admin password reset successfully!')
    print(f'   Rows updated: {result.rowcount}')
    print(f'   Username: admin')
    print(f'   Password: Passw0rd')
    print()

# Test login
print('Testing login...')
try:
    response = requests.post(
        'http://localhost:8080/api/auth/login',
        json={'username': 'admin', 'password': 'Passw0rd'},
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        print(f'✅ Login successful!')
        print(f'   Token: {data.get("access_token", "N/A")[:50]}...')
    else:
        print(f'❌ Login failed with status {response.status_code}')
        print(f'   Response: {response.text[:200]}')
except Exception as e:
    print(f'❌ Login test error: {e}')
