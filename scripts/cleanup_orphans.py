"""Удаляет файлы в data/storage/, на которые нет file_path в documents."""
import asyncio
from pathlib import Path

from sqlalchemy import select

from src.core.config import settings
from src.core.db import AsyncSessionLocal
from src.core.db.models import Document


async def main() -> None:
    async with AsyncSessionLocal() as db:
        used = set(
            (await db.execute(
                select(Document.file_path).where(Document.file_path.is_not(None))
            )).scalars().all()
        )

    base = Path(settings.storage_dir)
    removed = 0
    for p in base.rglob("*"):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        key = str(p.relative_to(base)).replace("\\", "/")
        if key not in used:
            p.unlink()
            removed += 1
            print(f"removed orphan: {key}")

    print(f"Done. Removed {removed} orphan file(s).")


if __name__ == "__main__":
    asyncio.run(main())