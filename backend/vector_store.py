from uuid import uuid4
from typing import Optional
import re

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

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 384

client = QdrantClient(path="./qdrant_data")

# Reranker
reranker = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


def create_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )


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


def store_chunks(
    chunks: list[dict],
    embeddings: list[list[float]]
):
    if len(chunks) != len(embeddings):
        raise ValueError(
            "Each chunk must have exactly one embedding."
        )

    points = []

    for chunk, embedding in zip(chunks, embeddings):
        point = PointStruct(
            id=str(uuid4()),
            vector=embedding,
            payload={
                "text": chunk["text"],
                **chunk["metadata"]
            }
        )
        points.append(point)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )


def search_chunks(
    query_embedding: list[float],
    limit: int = 3,
    document_name: Optional[str] = None
):
    query_filter = None

    if document_name:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_name",
                    match=MatchValue(
                        value=document_name
                    )
                )
            ]
        )

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


def search_chunks_bm25(
    query: str,
    limit: int = 3,
    document_name: Optional[str] = None
):
    query_filter = None

    if document_name:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_name",
                    match=MatchValue(
                        value=document_name
                    )
                )
            ]
        )

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
