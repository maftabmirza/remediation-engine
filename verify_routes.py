import sys
import os
import logging
from fastapi.routing import APIRoute

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_routes():
    try:
        logger.info("Importing app.main...")
        from app.main import app
        
        logger.info("Verifying routes...")
        found_ui = False
        found_api = False
        
        for route in app.routes:
            if isinstance(route, APIRoute):
                if route.path == "/incidents":
                    logger.info(f"✅ Found UI route: {route.path} -> {route.name}")
                    found_ui = True
                elif route.path == "/api/incidents":
                    logger.info(f"✅ Found API route: {route.path} -> {route.name}")
                    found_api = True
                    
        if found_ui and found_api:
            logger.info("🎉 All incident routes verified successfully!")
        else:
            if not found_ui:
                logger.error("❌ UI route /incidents NOT found")
            if not found_api:
                logger.error("❌ API route /api/incidents NOT found")
                
    except Exception as e:
        logger.error(f"❌ Failed to load app: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_routes()
