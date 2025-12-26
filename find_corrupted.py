import os
import sys

def check_for_null_bytes(directory):
    """Scan directory for Python files containing null bytes."""
    corrupted = []
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'rb') as f:
                        content = f.read()
                        if b'\x00' in content:
                            corrupted.append(filepath)
                            print(f"CORRUPTED: {filepath}")
                except Exception as e:
                    print(f"ERROR reading {filepath}: {e}")
    return corrupted

if __name__ == "__main__":
    dirs_to_scan = ['alembic', 'app']
    all_corrupted = []
    for d in dirs_to_scan:
        if os.path.exists(d):
            print(f"Scanning {d}...")
            all_corrupted.extend(check_for_null_bytes(d))
    
    if all_corrupted:
        print(f"\nFound {len(all_corrupted)} corrupted files!")
    else:
        print("\nNo corrupted files found.")
