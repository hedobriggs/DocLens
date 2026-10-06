import os
import json
import logging

from dotenv import load_dotenv
from google import genai


# --------------------------------------------------
# Logging
# --------------------------------------------------

logger = logging.getLogger("doclens")


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
) -> dict:

    if not retrieved_chunks:
        return {
            "answer": "I could not find relevant information in the documents.",
            "source_ids": []
        }

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

Return ONLY valid JSON in this exact format:

{{
  "answer": "your answer here",
  "source_ids": [1, 2]
}}

Rules:
- Do not use outside knowledge.
- Do not invent information.
- source_ids must contain only the source numbers
  that directly support the answer.
- Do not include irrelevant sources.
- If the context does not contain enough information
  to answer the question, say that the answer could
  not be found in the provided documents and return
  an empty source_ids list.
- Keep the answer clear and concise.

Question:
{question}

Document context:
{context}
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        response_text = response.text.strip()

        if response_text.startswith("```"):
            response_text = response_text.replace(
                "```json", ""
            ).replace(
                "```", ""
            ).strip()

        result = json.loads(response_text)

        return {
            "answer": result["answer"],
            "source_ids": result.get("source_ids", [])
        }

    except json.JSONDecodeError:
        logger.exception(
            "Gemini returned invalid JSON"
        )

        raise RuntimeError(
            "The AI service returned an invalid response."
        )

    except Exception:
        logger.exception(
            "Gemini generation request failed"
        )

        raise RuntimeError(
            "The AI service is temporarily unavailable."
        )
