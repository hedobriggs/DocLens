"""Publish complete vector revisions; never delete previous document points."""
from uuid import NAMESPACE_URL, uuid4, uuid5
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny, IsEmptyCondition, PayloadField

CATALOG = 'doclens_document_publications'


def pointer_id(name):
    return str(uuid5(NAMESPACE_URL, 'doclens.document.publication/' + name))


def ensure_collection(client, name, size, distance):
    if not client.collection_exists(name):
        try:
            client.create_collection(name, vectors_config=VectorParams(size=size, distance=distance))
        except Exception:
            if not client.collection_exists(name):
                raise


def publications(client, name=None):
    if not client.collection_exists(CATALOG):
        return {}
    if name is not None:
        points = client.retrieve(CATALOG, ids=[pointer_id(name)], with_payload=True, with_vectors=False)
    else:
        points = []
        offset = None
        while True:
            batch, offset = client.scroll(CATALOG, limit=256, offset=offset, with_payload=True, with_vectors=False)
            points.extend(batch)
            if offset is None:
                break
    return {p.payload['document_name']: p.payload['revision'] for p in points}


def visible_filter(client, name=None):
    current = publications(client, name)
    alternatives = []
    if current:
        alternatives.append(FieldCondition(key='_doclens_revision', match=MatchAny(any=list(current.values()))))
    legacy = Filter(must=[IsEmptyCondition(is_empty=PayloadField(key='_doclens_revision'))])
    if current:
        legacy.must_not = [FieldCondition(key='document_name', match=MatchAny(any=list(current)))]
    alternatives.append(legacy)
    conditions = [Filter(should=alternatives)]
    if name is not None:
        conditions.append(FieldCondition(key='document_name', match=MatchValue(value=name)))
    return Filter(must=conditions)


def replace(client, collection, name, chunks, vectors, check=lambda: None, stage=lambda name: None):
    if not chunks or len(chunks) != len(vectors):
        raise ValueError('Every document chunk requires one embedding')
    if any(c['metadata']['document_name'] != name for c in chunks):
        raise ValueError('Replacement chunks must belong to one document')
    check()
    stage('indexing')
    revision = str(uuid4())
    ensure_collection(client, collection, 384, Distance.COSINE)
    ensure_collection(client, CATALOG, 1, Distance.DOT)
    for start in range(0, len(chunks), 100):
        check()
        batch = [PointStruct(id=str(uuid4()), vector=v, payload={
            'text': c['text'], **c['metadata'], '_doclens_revision': revision,
        }) for c, v in zip(chunks[start:start+100], vectors[start:start+100])]
        client.upsert(collection, points=batch, wait=True)
    stage('publication')
    check()
    # One durable pointer becomes visible only after every batch has succeeded.
    # A lost acknowledgement can make the outcome uncertain; never roll back a
    # newer publication or delete any previous/staged points to compensate.
    client.upsert(CATALOG, points=[PointStruct(id=pointer_id(name), vector=[0.0],
        payload={'document_name': name, 'revision': revision})], wait=True)
