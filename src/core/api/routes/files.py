from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.models import Document
from src.core.db.session import get_db
from src.core.storage import get_storage
from src.core.storage.base import StorageBackend

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{document_id}")
async def download_file(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    doc = (await db.execute(
        select(Document).where(Document.id == document_id)
    )).scalar_one_or_none()

    if doc is None or not doc.file_path:
        raise HTTPException(404, "File not found")

    path = await storage.get_path(doc.file_path)
    if not path.exists():
        raise HTTPException(404, "File missing on disk")

    return FileResponse(
        path=path,
        media_type=doc.file_mime or "application/octet-stream",
        filename=doc.file_name or path.name,
    )