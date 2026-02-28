"""
Design Settings API - Manage custom logo and icon for the sidebar.
Images are stored in /static/images/ and config is persisted in a JSON file.
"""
import os
import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from app.models import User
from app.services.auth_service import get_current_user, require_permission

router = APIRouter(prefix="/api/design", tags=["Design"])

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STATIC_IMAGES_DIR = Path(__file__).parents[2] / "static" / "images"
STORAGE_DIR = Path(__file__).parents[2] / "storage" / "design"
UPLOAD_IMAGES_DIR = STORAGE_DIR / "images"  # writable volume (storage is not :ro)
SETTINGS_FILE = STORAGE_DIR / "design_settings.json"

# Default image paths (no built-in logo — upload via Settings → Design)
DEFAULT_LOGO = ""
DEFAULT_ICON = ""

# Allowed MIME types
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/svg+xml",
    "image/gif",
    "image/webp",
}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB


def _ensure_dirs():
    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _load_settings() -> dict:
    _ensure_dirs()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"logo_url": DEFAULT_LOGO, "icon_url": DEFAULT_ICON}


def _save_settings(data: dict):
    _ensure_dirs()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _ext_from_content_type(content_type: str) -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/svg+xml": ".svg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return mapping.get(content_type, ".png")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def get_design_settings():
    """Return current logo and icon URLs (public – needed by every page)."""
    return _load_settings()


@router.post("/upload/logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission(["manage_providers"])),
):
    """Upload a custom full logo (displayed in expanded sidebar)."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PNG, JPG, SVG, GIF, WEBP",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2 MB.",
        )

    ext = _ext_from_content_type(file.content_type)
    filename = f"custom_logo{ext}"
    dest = UPLOAD_IMAGES_DIR / filename

    # Remove old custom logos with different extensions
    for old in UPLOAD_IMAGES_DIR.glob("custom_logo.*"):
        old.unlink(missing_ok=True)

    with open(dest, "wb") as f:
        f.write(contents)

    logo_url = f"/uploaded-images/{filename}"
    settings = _load_settings()
    settings["logo_url"] = logo_url
    _save_settings(settings)

    return {"status": "ok", "logo_url": logo_url}


@router.post("/upload/icon")
async def upload_icon(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission(["manage_providers"])),
):
    """Upload a custom icon (displayed in collapsed sidebar)."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PNG, JPG, SVG, GIF, WEBP",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2 MB.",
        )

    ext = _ext_from_content_type(file.content_type)
    
    # Force 1:1 aspect ratio by padding with transparency
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(contents))
        width, height = img.size
        max_dim = max(width, height)
        
        new_img = Image.new("RGBA", (max_dim, max_dim), (255, 255, 255, 0))
        paste_x = (max_dim - width) // 2
        paste_y = (max_dim - height) // 2
        
        if img.mode != "RGBA":
            img = img.convert("RGBA")
            
        new_img.paste(img, (paste_x, paste_y), img)
        output_io = io.BytesIO()
        new_img.save(output_io, format="PNG")
        contents = output_io.getvalue()
        ext = ".png"
    except Exception as e:
        print(f"Error resizing icon: {e}")

    filename = f"custom_icon{ext}"
    dest = UPLOAD_IMAGES_DIR / filename

    # Remove old custom icons with different extensions
    for old in UPLOAD_IMAGES_DIR.glob("custom_icon.*"):
        old.unlink(missing_ok=True)

    with open(dest, "wb") as f:
        f.write(contents)

    icon_url = f"/uploaded-images/{filename}"
    settings = _load_settings()
    settings["icon_url"] = icon_url
    _save_settings(settings)

    return {"status": "ok", "icon_url": icon_url}


@router.delete("/reset")
async def reset_design(
    current_user: User = Depends(require_permission(["manage_providers"])),
):
    """Reset logo and/or icon back to the built-in defaults."""
    # Remove all custom uploads
    for pattern in ["custom_logo.*", "custom_icon.*"]:
        for f in STATIC_IMAGES_DIR.glob(pattern):
            f.unlink(missing_ok=True)

    defaults = {"logo_url": DEFAULT_LOGO, "icon_url": DEFAULT_ICON}
    _save_settings(defaults)
    return {"status": "ok", **defaults}


@router.delete("/reset/logo")
async def reset_logo(
    current_user: User = Depends(require_permission(["manage_providers"])),
):
    """Reset only the logo back to default."""
    for f in STATIC_IMAGES_DIR.glob("custom_logo.*"):
        f.unlink(missing_ok=True)

    settings = _load_settings()
    settings["logo_url"] = DEFAULT_LOGO
    _save_settings(settings)
    return {"status": "ok", "logo_url": DEFAULT_LOGO}


@router.delete("/reset/icon")
async def reset_icon(
    current_user: User = Depends(require_permission(["manage_providers"])),
):
    """Reset only the icon back to default."""
    for f in STATIC_IMAGES_DIR.glob("custom_icon.*"):
        f.unlink(missing_ok=True)

    settings = _load_settings()
    settings["icon_url"] = DEFAULT_ICON
    _save_settings(settings)
    return {"status": "ok", "icon_url": DEFAULT_ICON}
