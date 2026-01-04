
from app.database import SessionLocal
from app.models_dashboards import PrometheusPanel, PrometheusDatasource

def check_panels():
    db = SessionLocal()
    try:
        panel_ids = [
            '52bb7804-b88b-442b-8fa3-799fa925e6d2', 
            'e1294bd5-d3e7-45ee-b7b7-14c5fcd8384e'
        ]
        
        print("\n--- Panel Datasource Check ---")
        for pid in panel_ids:
            panel = db.query(PrometheusPanel).get(pid)
            if panel:
                ds = db.query(PrometheusDatasource).get(panel.datasource_id)
                print(f"Panel: {panel.name} ({panel.id})")
                if ds:
                    print(f"  Datasource: {ds.name}")
                    print(f"  URL: {ds.url}")
                    print(f"  Auth: {ds.auth_type}")
                else:
                    print(f"  Datasource ID: {panel.datasource_id} (NOT FOUND)")
            else:
                print(f"Panel {pid} not found")

    finally:
        db.close()

if __name__ == "__main__":
    check_panels()
