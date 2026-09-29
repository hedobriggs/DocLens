from uuid import uuid4
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)


COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 384


# --------------------------------------------------
# Qdrant client
# --------------------------------------------------

# Store Qdrant data locally inside backend/qdrant_data
client = QdrantClient(path="./qdrant_data")


# --------------------------------------------------
# Create collection
# --------------------------------------------------

def create_collection():
    """Create the document_chunks collection if it does not exist."""

    if not client.collection_exists(COLLECTION_NAME):

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )


# --------------------------------------------------
# Store chunks
# --------------------------------------------------

def store_chunks(
    chunks: list[dict],
    embeddings: list[list[float]]
):
    """Store document chunks and embeddings in Qdrant."""

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


# --------------------------------------------------
# Search chunks
# --------------------------------------------------

def search_chunks(
    query_embedding: list[float],
    limit: int = 3,
    document_name: Optional[str] = None
):
    """
    Search Qdrant for chunks similar to the query.

    If document_name is provided, only search
    chunks belonging to that document.
    """

    query_filter = None

    # Filter search to one document if requested
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
