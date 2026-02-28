
files = [
    r'd:\remediation-engine-vscode\entrypoint.sh',
    r'd:\remediation-engine-vscode\atlas\migrations\20260126000000_initial_schema.sql',
    r'd:\remediation-engine-vscode\app\models.py'
]
for f in files:
    try:
        with open(f, 'rb') as fp:
            content = fp.read()
            has_null = b'\x00' in content
            print(f"{f}: {'HAS NULLS' if has_null else 'OK'}")
    except Exception as e:
        print(f"{f}: Error {e}")
