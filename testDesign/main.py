from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

templates = Jinja2Templates(directory=".")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/troubleshoot", response_class=HTMLResponse)
async def read_troubleshoot(request: Request):
    return templates.TemplateResponse("troubleshoot.html", {"request": request})

@app.get("/llm-providers", response_class=HTMLResponse)
async def read_llm_providers(request: Request):
    return templates.TemplateResponse("llm_providers.html", {"request": request})

@app.get("/servers", response_class=HTMLResponse)
async def read_servers(request: Request):
    return templates.TemplateResponse("servers.html", {"request": request})

@app.get("/api-credentials", response_class=HTMLResponse)
async def read_api_credentials(request: Request):
    return templates.TemplateResponse("api_credentials.html", {"request": request})

@app.get("/credential-profiles", response_class=HTMLResponse)
async def read_credential_profiles(request: Request):
    return templates.TemplateResponse("credential_profiles.html", {"request": request})

@app.get("/authentication", response_class=HTMLResponse)
async def read_authentication(request: Request):
    return templates.TemplateResponse("authentication.html", {"request": request})

@app.get("/pii-detection", response_class=HTMLResponse)
async def read_pii_detection(request: Request):
    return templates.TemplateResponse("pii_detection.html", {"request": request})

@app.get("/pii-logs", response_class=HTMLResponse)
async def read_pii_logs(request: Request):
    return templates.TemplateResponse("pii_logs.html", {"request": request})

@app.get("/alerts", response_class=HTMLResponse)
async def read_alerts(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})

@app.get("/audit", response_class=HTMLResponse)
async def read_audit(request: Request):
    return templates.TemplateResponse("audit.html", {"request": request})

@app.get("/{page}")
async def read_page(request: Request, page: str):
    # 1. If it's a direct file match (like styles.css), serve it
    if os.path.isfile(page):
        return FileResponse(page)
    
    # 2. If it maps to an HTML file (clean URL), render it
    html_path = f"{page}.html"
    if os.path.isfile(html_path):
        return templates.TemplateResponse(html_path, {"request": request})
        
    return HTMLResponse(content="Page not found", status_code=404)

# Mount the current directory to serve static files (CSS, JS, etc.) from the root
app.mount("/", StaticFiles(directory="."), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
