from __future__ import annotations

from collections import defaultdict

from src.core.rag.vector_search import SearchHit


def reciprocal_rank_fusion(
    hit_lists: list[list[SearchHit]],
    k: int = 60,
    top_k: int = 10,
) -> list[SearchHit]:
    """
    Сливает несколько ранжированных списков в один.
    Возвращает новые SearchHit с пересчитанным rank и rrf_score.
    """
    scores: dict[int, float] = defaultdict(float)
    # сохраняем "лучший" оригинальный хит по chunk_id, чтобы вернуть его данные
    best_hit: dict[int, SearchHit] = {}
    # для отладки: какие источники голосовали за чанк
    sources: dict[int, set[str]] = defaultdict(set)

    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            scores[hit.chunk_id] += 1.0 / (k + rank)
            sources[hit.chunk_id].add(hit.source)
            # сохраняем хит с наибольшим raw_score (для наглядности)
            if hit.chunk_id not in best_hit or hit.raw_score > best_hit[hit.chunk_id].raw_score:
                best_hit[hit.chunk_id] = hit

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    result: list[SearchHit] = []
    for final_rank, (chunk_id, rrf_score) in enumerate(fused, start=1):
        base = best_hit[chunk_id]
        result.append(
            SearchHit(
                chunk_id=base.chunk_id,
                document_id=base.document_id,
                content=base.content,
                title=base.title,
                url=base.url,
                rank=final_rank,
                raw_score=rrf_score,  # теперь это RRF-оценка, а не similarity
                source="+".join(sorted(sources[chunk_id])),
            )
        )
    return result