"""Fix WinRM SSL setting for server on port 5985."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # Update WinRM server to use HTTP (not SSL) on port 5985
    result = conn.execute(text("""
        UPDATE server_credentials 
        SET winrm_use_ssl = false, winrm_cert_validation = false 
        WHERE protocol = 'winrm' AND port = 5985
    """))
    conn.commit()
    print(f"Updated {result.rowcount} WinRM server(s) to use HTTP (not SSL)")
    
    # Show current settings
    rows = conn.execute(text("""
        SELECT hostname, port, winrm_use_ssl, winrm_cert_validation 
        FROM server_credentials 
        WHERE protocol = 'winrm'
    """)).fetchall()
    
    print("\nCurrent WinRM servers:")
    for row in rows:
        print(f"  {row[0]}:{row[1]} - SSL={row[2]}, CertValidation={row[3]}")
