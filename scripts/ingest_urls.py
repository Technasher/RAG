# scripts/ingest_urls.py
import asyncio
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from src.core.config import settings
from src.core.db import AsyncSessionLocal
from src.core.rag.embeddings import build_embedder
from src.core.rag.ingest import ingest_text


async def ingest_url(db, url: str, embedder, source_type: str = "web") -> dict:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = soup.get_text("\n", strip=True)

    return await ingest_text(
        db,
        title=title,
        text=text,
        source_type=source_type,
        source_url=url,
        external_id=url,       # URL — стабильный external_id
        embedder=embedder,
        settings=settings,
    )


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ingest_urls <url> [<url> ...]")
        return

    embedder = build_embedder(settings)
    async with AsyncSessionLocal() as db:
        for url in sys.argv[1:]:
            try:
                result = await ingest_url(db, url, embedder)
                print(f"[ok] {url} -> {result}")
            except Exception as exc:
                print(f"[error] {url}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
