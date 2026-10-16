from observability import measure, TOKENS, COST, COST_SKIPPED
import os
import json
import logging
import math

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

# Ingestion, health and metrics remain usable without a hosted-generation key.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def _record_usage(usage):
    if usage is None:
        COST_SKIPPED.labels("usage_unavailable").inc()
        return
    input_tokens = usage.prompt_token_count
    output_tokens = usage.candidates_token_count
    if input_tokens is not None:
        TOKENS.labels("input").inc(input_tokens)
    if output_tokens is not None:
        TOKENS.labels("output").inc(output_tokens)
    raw = [os.getenv("GEMINI_INPUT_USD_PER_MILLION"), os.getenv("GEMINI_OUTPUT_USD_PER_MILLION")]
    if all(value is None for value in raw):
        COST_SKIPPED.labels("not_configured").inc()
        return
    if any(value is None for value in raw):
        COST_SKIPPED.labels("incomplete").inc()
        return
    try:
        prices = [float(value) for value in raw]
    except (ValueError, TypeError, OverflowError):
        COST_SKIPPED.labels("invalid").inc()
        return
    if any(not math.isfinite(price) or price < 0 for price in prices):
        COST_SKIPPED.labels("invalid").inc()
        return
    if input_tokens is None or output_tokens is None:
        COST_SKIPPED.labels("usage_unavailable").inc()
        return
    cost = input_tokens / 1_000_000 * prices[0] + output_tokens / 1_000_000 * prices[1]
    if not math.isfinite(cost):
        COST_SKIPPED.labels("overflow").inc()
        return
    COST.labels("USD").inc(cost)


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
        with measure("gemini"):
            if client is None:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite", contents=prompt
            )
            # Include JSON/schema failures in operation error metrics.
            raw = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            if not isinstance(parsed.get("answer"), str) or not isinstance(parsed.get("source_ids", []), list):
                raise ValueError("Invalid Gemini response schema")
        _record_usage(response.usage_metadata)

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
        logger.error(
            "Gemini returned invalid JSON"
        )

        raise RuntimeError(
            "The AI service returned an invalid response."
        ) from None

    except Exception:
        logger.error(
            "Gemini generation request failed"
        )

        raise RuntimeError(
            "The AI service is temporarily unavailable."
        ) from None
