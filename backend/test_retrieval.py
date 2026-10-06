from embeddings import create_embedding
from vector_store import hybrid_search

questions = [
    "How to care for the television?",
    "How far should I be from the TV when using the remote?"
]

for question in questions:
    print("\nQUESTION:", question)

    results = hybrid_search(
        query=question,
        query_embedding=create_embedding(question),
        limit=10,
        document_name="Sansung User Manual.pdf"
    )

    for rank, result in enumerate(results, start=1):
        print(
            rank,
            "Page:", result.payload["page_number"],
            "Chunk:", result.payload["chunk_id"]
        )
