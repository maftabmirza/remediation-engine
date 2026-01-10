from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv
import sys

# Add current directory to path
sys.path.append(os.getcwd())

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops")

def dump_schema():
    print(f"Connecting to {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    output_file = "current_schema.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Database Schema Dump - {os.getenv('DATABASE_NAME', 'aiops')}\n")
        f.write("="*50 + "\n\n")
        
        table_names = inspector.get_table_names()
        for table_name in sorted(table_names):
            f.write(f"Table: {table_name}\n")
            f.write("-" * (len(table_name) + 7) + "\n")
            
            # Columns
            columns = inspector.get_columns(table_name)
            f.write("Columns:\n")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f"DEFAULT {col['default']}" if col['default'] else ""
                f.write(f"  - {col['name']} ({col['type']}) {nullable} {default}\n")
            
            # Primary Keys
            pk = inspector.get_pk_constraint(table_name)
            if pk and pk['constrained_columns']:
                f.write(f"Primary Key: {', '.join(pk['constrained_columns'])}\n")
            
            # Foreign Keys
            fks = inspector.get_foreign_keys(table_name)
            if fks:
                f.write("Foreign Keys:\n")
                for fk in fks:
                    f.write(f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}\n")
            
            # Indexes
            indexes = inspector.get_indexes(table_name)
            if indexes:
                f.write("Indexes:\n")
                for idx in indexes:
                    unique = "UNIQUE " if idx['unique'] else ""
                    f.write(f"  - {idx['name']}: {unique}({', '.join(idx['column_names'])})\n")
            
            f.write("\n" + "="*50 + "\n\n")
            
    print(f"Schema dumped to {output_file}")

if __name__ == "__main__":
    dump_schema()
