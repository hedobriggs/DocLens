from observability import measure, DOCUMENTS, CHUNKS
from uuid import uuid4
from typing import Optional
import re
import sqlite3
import logging
from contextlib import closing
from functools import wraps
from pathlib import Path
from threading import RLock

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
    MatchAny,
    IsEmptyCondition,
    PayloadField,
)

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 384

# One owning process, with every local read/write protected by the same lock.
# Disabling the SQLite thread check alone would NOT make local Qdrant thread-safe.
_storage_lock = RLock()
client = QdrantClient(path="./qdrant_data", force_disable_check_same_thread=True)
_catalog_path = Path("./qdrant_data/publications.sqlite")
with closing(sqlite3.connect(_catalog_path)) as catalog, catalog:
    catalog.execute("CREATE TABLE IF NOT EXISTS publications (document_name TEXT PRIMARY KEY, revision TEXT NOT NULL)")


def serialized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _storage_lock:
            return function(*args, **kwargs)
    return wrapped


def _publications():
    with closing(sqlite3.connect(_catalog_path)) as catalog, catalog:
        return dict(catalog.execute("SELECT document_name, revision FROM publications"))


def _publish(document_name, revision):
    # The visibility change is one durable SQLite transaction, after vector writes.
    with closing(sqlite3.connect(_catalog_path)) as catalog, catalog:
        catalog.execute("PRAGMA synchronous=FULL")
        catalog.execute("INSERT INTO publications VALUES (?, ?) ON CONFLICT(document_name) DO UPDATE SET revision=excluded.revision",
                        (document_name, revision))


def _visible_filter(document_name=None):
    publications = _publications()
    alternatives = []
    if publications:
        alternatives.append(FieldCondition(key="_doclens_revision", match=MatchAny(any=list(publications.values()))))
    # Existing unversioned chunks remain searchable until their document is replaced.
    legacy = Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="_doclens_revision"))])
    if publications:
        legacy.must_not = [FieldCondition(key="document_name", match=MatchAny(any=list(publications)))]
    alternatives.append(legacy)
    conditions = [Filter(should=alternatives)]
    if document_name:
        conditions.append(FieldCondition(key="document_name", match=MatchValue(value=document_name)))
    return Filter(must=conditions)


@serialized
def replace_document(document_name, chunks, embeddings):
    if not chunks or len(chunks) != len(embeddings):
        raise ValueError("Each non-empty document chunk must have exactly one embedding.")
    if any(chunk["metadata"]["document_name"] != document_name for chunk in chunks):
        raise ValueError("All chunks must belong to the document being replaced.")
    # Validate point payloads before writes. Fresh IDs cannot overwrite old data.
    revision = str(uuid4())
    points = [PointStruct(id=str(uuid4()), vector=embedding,
                          payload={"text": chunk["text"], **chunk["metadata"], "_doclens_revision": revision})
              for chunk, embedding in zip(chunks, embeddings)]
    create_collection()
    client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    _publish(document_name, revision)
    # Unpublished/retired chunks are deliberately retained: never delete a previous
    # searchable revision before publication. A future durable GC job can reclaim them.
    try:
        refresh_storage_metrics()
    except Exception:
        # A telemetry failure after commit must not report successful publication
        # as a failed upload. Never include document content or identifiers here.
        logging.getLogger("doclens").warning("Published document; storage metric refresh failed")

# Reranker
reranker = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


@serialized
def refresh_storage_metrics():
    if not client.collection_exists(COLLECTION_NAME):
        DOCUMENTS.labels(COLLECTION_NAME).set(0)
        CHUNKS.labels(COLLECTION_NAME).set(0)
        return
    names = set()
    total = 0
    offset = None
    while True:
        points, offset = client.scroll(COLLECTION_NAME, scroll_filter=_visible_filter(), offset=offset, limit=256,
                                       with_payload=["document_name"], with_vectors=False)
        total += len(points)
        names.update(p.payload.get("document_name") for p in points)
        if offset is None:
            break
    DOCUMENTS.labels(COLLECTION_NAME).set(len(names))
    CHUNKS.labels(COLLECTION_NAME).set(total)


@serialized
def create_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )

    refresh_storage_metrics()


@serialized
def delete_document(document_name: str):
    if not client.collection_exists(COLLECTION_NAME):
        return

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_name",
                        match=MatchValue(
                            value=document_name
                        )
                    )
                ]
            )
        )
    )

    with closing(sqlite3.connect(_catalog_path)) as catalog, catalog:
        catalog.execute("DELETE FROM publications WHERE document_name=?", (document_name,))
    refresh_storage_metrics()


@serialized
def store_chunks(
    chunks: list[dict],
    embeddings: list[list[float]]
):
    if len(chunks) != len(embeddings):
        raise ValueError("Each chunk must have exactly one embedding.")
    documents = {}
    for chunk, embedding in zip(chunks, embeddings):
        batch = documents.setdefault(chunk["metadata"]["document_name"], ([], []))
        batch[0].append(chunk)
        batch[1].append(embedding)
    for name, (document_chunks, vectors) in documents.items():
        replace_document(name, document_chunks, vectors)


@serialized
def search_chunks(
    query_embedding: list[float],
    limit: int = 3,
    document_name: Optional[str] = None
):
    query_filter = _visible_filter(document_name)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=query_filter,
        limit=limit
    )

    return results.points


def tokenize(text: str) -> list[str]:
    return re.findall(
        r"\b\w+\b",
        text.lower()
    )


@serialized
def search_chunks_bm25(
    query: str,
    limit: int = 3,
    document_name: Optional[str] = None
):
    query_filter = _visible_filter(document_name)

    points = []
    offset = None

    while True:
        batch, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )

        points.extend(batch)

        if offset is None:
            break

    if not points:
        return []

    tokenized_chunks = [
        tokenize(point.payload["text"])
        for point in points
    ]

    bm25 = BM25Okapi(tokenized_chunks)

    query_tokens = tokenize(query)

    scores = bm25.get_scores(query_tokens)

    ranked = sorted(
        zip(points, scores),
        key=lambda item: item[1],
        reverse=True
    )

    return ranked[:limit]


@serialized
def hybrid_search(
    query: str,
    query_embedding: list[float],
    limit: int = 3,
    document_name: Optional[str] = None
):
    candidate_limit = 20
    rrf_k = 60

    dense_weight = 2.0
    bm25_weight = 1.0

    # --------------------------------------------
    # Dense retrieval
    # --------------------------------------------

    dense_results = search_chunks(
        query_embedding=query_embedding,
        limit=candidate_limit,
        document_name=document_name
    )

    # --------------------------------------------
    # BM25 retrieval
    # --------------------------------------------

    bm25_results = search_chunks_bm25(
        query=query,
        limit=candidate_limit,
        document_name=document_name
    )

    # --------------------------------------------
    # Reciprocal Rank Fusion
    # --------------------------------------------

    rrf_scores = {}
    points = {}

    for rank, point in enumerate(
        dense_results,
        start=1
    ):
        key = (
            point.payload["document_name"],
            point.payload["chunk_id"]
        )

        points[key] = point

        rrf_scores[key] = (
            rrf_scores.get(key, 0)
            + dense_weight / (rrf_k + rank)
        )

    for rank, (point, _) in enumerate(
        bm25_results,
        start=1
    ):
        key = (
            point.payload["document_name"],
            point.payload["chunk_id"]
        )

        points[key] = point

        rrf_scores[key] = (
            rrf_scores.get(key, 0)
            + bm25_weight / (rrf_k + rank)
        )

    ranked_keys = sorted(
        rrf_scores,
        key=rrf_scores.get,
        reverse=True
    )

    # Keep the best hybrid candidates for reranking
    candidates = [
        points[key]
        for key in ranked_keys[:candidate_limit]
    ]

    if not candidates:
        return []

    # --------------------------------------------
    # Cross-encoder reranking
    # --------------------------------------------

    pairs = [
        (
            query,
            point.payload["text"]
        )
        for point in candidates
    ]

    with measure("reranking"):
        rerank_scores = reranker.predict(pairs)

    reranked = sorted(
        zip(candidates, rerank_scores),
        key=lambda item: float(item[1]),
        reverse=True
    )

    # Return only the best final chunks
    return [
        point
        for point, _ in reranked[:limit]
    ]


refresh_storage_metrics()
