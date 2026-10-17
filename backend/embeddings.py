
import logging
import time
import os
import torch
from threading import RLock
inference_lock = RLock()
INFERENCE_THREADS = int(os.getenv("DOCLENS_INFERENCE_THREADS", "2"))
if not 1 <= INFERENCE_THREADS <= 4:
    raise ValueError("DOCLENS_INFERENCE_THREADS must be between 1 and 4")
torch.set_num_threads(INFERENCE_THREADS)
torch.set_num_interop_threads(1)

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 32

logger = logging.getLogger("doclens")

# Load the embedding model once
model = SentenceTransformer(MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    """Create an embedding for one piece of text."""
    with inference_lock:
        embedding = model.encode(text)
    return embedding.tolist()


def create_embeddings(texts: list[str], check=lambda: None) -> list[list[float]]:
    """Create embeddings in manageable batches."""

    if not texts:
        return []

    total = len(texts)
    embeddings = []
    start_time = time.perf_counter()

    logger.info(
        "Embedding started | total_chunks=%d | batch_size=%d",
        total,
        BATCH_SIZE,
    )

    for start in range(0, total, BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]

        check()
        with inference_lock:
            check()
            batch_embeddings = model.encode(
                batch, batch_size=BATCH_SIZE, show_progress_bar=False,
            )
        check()

        embeddings.extend(batch_embeddings.tolist())

        logger.info(
            "Embedding progress | completed=%d | total=%d | elapsed=%.1fs",
            min(start + len(batch), total),
            total,
            time.perf_counter() - start_time,
        )

    logger.info(
        "Embedding completed | total_chunks=%d | elapsed=%.1fs",
        total,
        time.perf_counter() - start_time,
    )

    return embeddings
