"""Bounded, read-only coverage of one published document for exhaustive questions."""
import re

MAX_COVERAGE_CHUNKS = 1500
MAX_COVERAGE_CHARACTERS = 120_000


class CoverageUnavailable(ValueError):
    pass


def needs_document_coverage(question):
    return bool(re.search(
        r'\b(?:all|every|each|complete|comprehensive|entire|exhaustive|'
        r'list|enumerate|count|overall|altogether)\b|'
        r'\bhow\s+many\b|\b(?:total|number)\s+of\b',
        question, re.IGNORECASE,
    ))


def gather_document(client, collection, document_name, visibility):
    if not document_name:
        raise CoverageUnavailable('Select one document for a comprehensive question.')
    if not client.collection_exists(collection):
        return []
    results, characters, offset = [], 0, None
    while True:
        batch, offset = client.scroll(
            collection_name=collection, scroll_filter=visibility,
            limit=64, offset=offset, with_payload=True, with_vectors=False,
        )
        for point in batch:
            payload = point.payload or {}
            text = payload.get('text')
            if (payload.get('document_name') != document_name or
                    not isinstance(text, str) or not text.strip() or
                    payload.get('page_number') is None or payload.get('chunk_id') is None):
                raise CoverageUnavailable('Document coverage is incomplete; re-indexing requires separate review.')
            characters += len(text)
            if len(results) >= MAX_COVERAGE_CHUNKS or characters > MAX_COVERAGE_CHARACTERS:
                raise CoverageUnavailable(
                    'Complete document context exceeds the bounded answer budget. '
                    'Ask a narrower question; no partial list was generated.'
                )
            results.append(point)
        if offset is None:
            break
    return sorted(results, key=lambda p: (
        p.payload['page_number'], str(p.payload['chunk_id']), str(p.id),
    ))
