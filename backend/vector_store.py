
import logging
import re
import time
from typing import Optional
from uuid import uuid4
from document_publication import visible_filter, replace as publish_replacement

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
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 384
QDRANT_BATCH_SIZE = 100

logger = logging.getLogger("doclens")

# Connect to the dedicated Qdrant Docker container.
client = QdrantClient(
    url="http://qdrant:6333",
    timeout=10,
)

# Load the reranker only when it is needed.
# This avoids downloading/loading the model when simply
# listing documents or storing chunks.
_reranker = None


def get_reranker():
    global _reranker

    if _reranker is None:
        logger.info("Loading reranking model")
        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    return _reranker


# --------------------------------------------------
# Collection management
# --------------------------------------------------

def create_collection():
    """Create the Qdrant collection if it does not exist."""

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

        logger.info(
            "Qdrant collection created | collection=%s",
            COLLECTION_NAME,
        )


def delete_document(document_name: str):
    """Delete all indexed chunks belonging to a document."""

    if not client.collection_exists(COLLECTION_NAME):
        return

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_name",
                        match=MatchValue(value=document_name),
                    )
                ]
            )
        ),
        wait=True,
    )

    logger.info(
        "Document deleted from Qdrant | document=%s",
        document_name,
    )


# --------------------------------------------------
# Document storage
# --------------------------------------------------

def replace_document(name, chunks, embeddings, check=lambda: None, stage=lambda name: None):
    return publish_replacement(client, COLLECTION_NAME, name, chunks, embeddings, check, stage)


def store_chunks(chunks, embeddings):
    if len(chunks) != len(embeddings):
        raise ValueError('Chunks and embeddings must have the same length')
    groups = {}
    for chunk, vector in zip(chunks, embeddings):
        group = groups.setdefault(chunk['metadata']['document_name'], ([], []))
        group[0].append(chunk); group[1].append(vector)
    for name, (parts, vectors) in groups.items():
        replace_document(name, parts, vectors)


# --------------------------------------------------
# Dense vector search
# --------------------------------------------------

def search_chunks(
    query_embedding,
    limit: int = 3,
    document_name: Optional[str] = None,
):
    """Search for semantically similar document chunks."""

    if not client.collection_exists(COLLECTION_NAME):
        return []

    query_filter = visible_filter(client, document_name)

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    return response.points


# --------------------------------------------------
# BM25 keyword search
# --------------------------------------------------

def search_chunks_bm25(
    query: str,
    limit: int = 3,
    document_name: Optional[str] = None,
):
    """Search document chunks using BM25 keyword matching."""

    if not client.collection_exists(COLLECTION_NAME):
        return []

    query_filter = visible_filter(client, document_name)

    all_points = []
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        all_points.extend(points)

        if offset is None:
            break

    if not all_points:
        return []

    tokenized_corpus = [
        re.findall(
            r"\w+",
            (point.payload or {}).get(
                "text",
                "",
            ).lower(),
        )
        for point in all_points
    ]

    if not any(tokenized_corpus):
        return []

    bm25 = BM25Okapi(tokenized_corpus)

    tokenized_query = re.findall(
        r"\w+",
        query.lower(),
    )

    if not tokenized_query:
        return []

    scores = bm25.get_scores(tokenized_query)

    ranked_indices = sorted(
        range(len(all_points)),
        key=lambda index: scores[index],
        reverse=True,
    )

    return [
        all_points[index]
        for index in ranked_indices[:limit]
        if scores[index] > 0
    ]


# --------------------------------------------------
# Hybrid search with reranking
# --------------------------------------------------

def hybrid_search(
    query: str,
    query_embedding,
    limit: int = 3,
    document_name: Optional[str] = None,
):
    """
    Combine dense vector search and BM25 keyword search
    using reciprocal rank fusion, then rerank results.
    """

    candidate_limit = max(limit * 4, 10)

    dense_results = search_chunks(
        query_embedding=query_embedding,
        limit=candidate_limit,
        document_name=document_name,
    )

    bm25_results = search_chunks_bm25(
        query=query,
        limit=candidate_limit,
        document_name=document_name,
    )

    # Reciprocal rank fusion.
    fusion_scores = {}
    points_by_id = {}

    RRF_K = 60

    for results in (dense_results, bm25_results):
        for rank, point in enumerate(results, start=1):
            point_id = str(point.id)

            points_by_id[point_id] = point

            fusion_scores[point_id] = (
                fusion_scores.get(point_id, 0.0)
                + 1.0 / (RRF_K + rank)
            )

    if not fusion_scores:
        return []

    ranked_ids = sorted(
        fusion_scores,
        key=fusion_scores.get,
        reverse=True,
    )

    candidates = [
        points_by_id[point_id]
        for point_id in ranked_ids[:candidate_limit]
    ]

    pairs = [
        [
            query,
            (point.payload or {}).get("text", ""),
        ]
        for point in candidates
    ]

    from embeddings import inference_lock
    with inference_lock:
        rerank_scores = get_reranker().predict(pairs)

    reranked = sorted(
        zip(candidates, rerank_scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )

    return [
        point
        for point, _score in reranked[:limit]
    ]


# --------------------------------------------------
# Persistent document listing
# --------------------------------------------------

def list_documents():
    """List indexed documents stored in Qdrant."""

    if not client.collection_exists(COLLECTION_NAME):
        return []

    documents = {}
    query_filter = visible_filter(client)
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            scroll_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}

            name = payload.get("document_name")

            if name:
                documents[name] = (
                    documents.get(name, 0) + 1
                )

        if offset is None:
            break

    return [
        {
            "name": name,
            "status": "Ready",
            "chunks": count,
        }
        for name, count in sorted(
            documents.items()
        )
    ]

