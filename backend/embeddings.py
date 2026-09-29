from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

# Load the embedding model once
model = SentenceTransformer(MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    """Create an embedding for one piece of text."""

    embedding = model.encode(text)

    return embedding.tolist()


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Create embeddings for multiple pieces of text."""

    embeddings = model.encode(texts)

    return embeddings.tolist()
