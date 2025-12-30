
files = [
    r'd:\remediate-engine-antigravity\entrypoint.sh',
    r'd:\remediate-engine-antigravity\alembic\versions\019_add_incident_metrics.py',
    r'd:\remediate-engine-antigravity\app\models.py'
]
for f in files:
    try:
        with open(f, 'rb') as fp:
            content = fp.read()
            has_null = b'\x00' in content
            print(f"{f}: {'HAS NULLS' if has_null else 'OK'}")
    except Exception as e:
        print(f"{f}: Error {e}")
