"""
Playlists API

API endpoints for managing dashboard playlists and auto-rotation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models_dashboards import Playlist, PlaylistItem, Dashboard

router = APIRouter(
    prefix="/api/playlists",
    tags=["playlists"]
)


# Pydantic schemas
class PlaylistItemCreate(BaseModel):
    dashboard_id: str
    order: int = 0
    custom_interval: Optional[int] = None


class PlaylistItemResponse(BaseModel):
    id: str
    dashboard_id: str
    dashboard_name: str
    order: int
    custom_interval: Optional[int]

    class Config:
        from_attributes = True


class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    interval: int = 30
    loop: bool = True


class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    interval: Optional[int] = None
    loop: Optional[bool] = None


class PlaylistResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    interval: int
    loop: bool
    created_at: str
    item_count: int

    class Config:
        from_attributes = True


class PlaylistDetailResponse(PlaylistResponse):
    items: List[PlaylistItemResponse]


@router.post("", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
async def create_playlist(
    playlist_data: PlaylistCreate,
    db: Session = Depends(get_db)
):
    """Create a new playlist."""
    new_playlist = Playlist(
        id=str(uuid.uuid4()),
        name=playlist_data.name,
        description=playlist_data.description,
        interval=playlist_data.interval,
        loop=playlist_data.loop
    )

    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)

    return PlaylistResponse(
        id=new_playlist.id,
        name=new_playlist.name,
        description=new_playlist.description,
        interval=new_playlist.interval,
        loop=new_playlist.loop,
        created_at=new_playlist.created_at.isoformat() if new_playlist.created_at else "",
        item_count=0
    )


@router.get("", response_model=List[PlaylistResponse])
async def list_playlists(db: Session = Depends(get_db)):
    """List all playlists."""
    playlists = db.query(Playlist).order_by(Playlist.created_at.desc()).all()

    return [
        PlaylistResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            interval=p.interval,
            loop=p.loop,
            created_at=p.created_at.isoformat() if p.created_at else "",
            item_count=len(p.items)
        )
        for p in playlists
    ]


@router.get("/{playlist_id}", response_model=PlaylistDetailResponse)
async def get_playlist(
    playlist_id: str,
    db: Session = Depends(get_db)
):
    """Get playlist details with all items."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    items_data = []
    for item in playlist.items:
        dashboard = db.query(Dashboard).filter(Dashboard.id == item.dashboard_id).first()
        if dashboard:
            items_data.append(PlaylistItemResponse(
                id=item.id,
                dashboard_id=item.dashboard_id,
                dashboard_name=dashboard.name,
                order=item.order,
                custom_interval=item.custom_interval
            ))

    return PlaylistDetailResponse(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        interval=playlist.interval,
        loop=playlist.loop,
        created_at=playlist.created_at.isoformat() if playlist.created_at else "",
        item_count=len(items_data),
        items=items_data
    )


@router.put("/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: str,
    playlist_update: PlaylistUpdate,
    db: Session = Depends(get_db)
):
    """Update playlist settings."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    update_data = playlist_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playlist, field, value)

    db.commit()
    db.refresh(playlist)

    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        interval=playlist.interval,
        loop=playlist.loop,
        created_at=playlist.created_at.isoformat() if playlist.created_at else "",
        item_count=len(playlist.items)
    )


@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    db: Session = Depends(get_db)
):
    """Delete a playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    db.delete(playlist)
    db.commit()

    return {"message": "Playlist deleted successfully"}


@router.post("/{playlist_id}/items", response_model=PlaylistItemResponse)
async def add_playlist_item(
    playlist_id: str,
    item_data: PlaylistItemCreate,
    db: Session = Depends(get_db)
):
    """Add a dashboard to the playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    dashboard = db.query(Dashboard).filter(Dashboard.id == item_data.dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    new_item = PlaylistItem(
        id=str(uuid.uuid4()),
        playlist_id=playlist_id,
        dashboard_id=item_data.dashboard_id,
        order=item_data.order,
        custom_interval=item_data.custom_interval
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return PlaylistItemResponse(
        id=new_item.id,
        dashboard_id=new_item.dashboard_id,
        dashboard_name=dashboard.name,
        order=new_item.order,
        custom_interval=new_item.custom_interval
    )


@router.delete("/{playlist_id}/items/{item_id}")
async def remove_playlist_item(
    playlist_id: str,
    item_id: str,
    db: Session = Depends(get_db)
):
    """Remove a dashboard from the playlist."""
    item = db.query(PlaylistItem).filter(
        PlaylistItem.id == item_id,
        PlaylistItem.playlist_id == playlist_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")

    db.delete(item)
    db.commit()

    return {"message": "Item removed from playlist"}
