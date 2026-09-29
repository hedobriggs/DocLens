import os

from dotenv import load_dotenv
from google import genai


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY was not found in the environment."
    )


# --------------------------------------------------
# Gemini client
# --------------------------------------------------

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# --------------------------------------------------
# Generate grounded answer
# --------------------------------------------------

def generate_answer(
    question: str,
    retrieved_chunks: list
) -> str:
    """
    Generate an answer using only the retrieved
    document chunks as context.
    """

    if not retrieved_chunks:
        return "I could not find relevant information in the documents."

    context_parts = []

    for index, result in enumerate(
        retrieved_chunks,
        start=1
    ):
        payload = result.payload

        context_parts.append(
            f"""
Source {index}
Document: {payload['document_name']}
Page: {payload['page_number']}

{payload['text']}
""".strip()
        )

    context = "\n\n".join(context_parts)

    prompt = f"""
You are the answer generation component of DocLens,
a document question-answering system.

Answer the user's question using only the document
context provided below.

Rules:
- Do not use outside knowledge.
- Do not invent information.
- If the context does not contain enough information
  to answer the question, say that the answer could
  not be found in the provided documents.
- Keep the answer clear and concise.

Question:
{question}

Document context:
{context}
""".strip()

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text
