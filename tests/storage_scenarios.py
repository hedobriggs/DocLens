"""Isolated HTTP scenarios: real Qdrant/SQLite, deterministic model substitutes."""
import importlib
import os
from pathlib import Path
import sqlite3
import json
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import fitz
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

scenario = sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    sentence = ModuleType('sentence_transformers')
    sentence.CrossEncoder = Mock(return_value=Mock(predict=lambda pairs: [1.] * len(pairs)))
    sys.modules['sentence_transformers'] = sentence
    embedding = ModuleType('embeddings')
    embedding.create_embedding = lambda _: [1.] + [0.] * 383
    barrier = None
    def encode(texts):
        if barrier:
            barrier.wait(timeout=10)
        return [[1.] + [0.] * 383 for _ in texts]
    embedding.create_embeddings = encode
    sys.modules['embeddings'] = embedding
    generation = ModuleType('generation'); generation.generate_answer = Mock()
    sys.modules['generation'] = generation
    os.environ['DOCLENS_SESSION_SECRET'] = 'synthetic-concurrency-tests-only-key'
    import main
    import vector_store as store
    headers = {'X-DocLens-Internal-Key': os.environ['DOCLENS_SESSION_SECRET']}
    def pdf(text, pages=1):
        with fitz.open() as document:
            for _ in range(pages):
                document.new_page().insert_textbox((36,36,560,800), text)
            return document.tobytes()
    def upload(api, name, text, pages=1):
        response = api.post('/documents/process', headers=headers,
                            files={'file':(name, pdf(text,pages), 'application/pdf')})
        assert response.status_code == 200, response.text
        return response.json()
    def visible(name=None):
        points, _ = store.client.scroll(store.COLLECTION_NAME,
            scroll_filter=store._visible_filter(name), limit=10000, with_payload=True)
        return points
    def check_counts(documents, chunks):
        store.refresh_storage_metrics()
        text = generate_latest().decode()
        assert f'doclens_documents{{collection="document_chunks"}} {documents}.0' in text, text
        assert f'doclens_chunks{{collection="document_chunks"}} {chunks}.0' in text, text
    def restart():
        expected = sorted(p.id for p in visible())
        store.client.close()
        script = """
import sys, types, json
from unittest.mock import Mock
sys.path.insert(0, sys.argv[1])
sentence=types.ModuleType('sentence_transformers'); sentence.CrossEncoder=Mock()
sys.modules['sentence_transformers']=sentence
import vector_store as store
points,_=store.client.scroll(store.COLLECTION_NAME,scroll_filter=store._visible_filter(),limit=10000)
assert sorted(p.id for p in points)==json.loads(sys.argv[2])
store.refresh_storage_metrics()
store.client.close()
"""
        process = subprocess.run([sys.executable,'-c',script,str(ROOT/'backend'),json.dumps(expected)],capture_output=True,text=True,timeout=20)
        assert process.returncode == 0, process.stdout + process.stderr
        store.client = store.QdrantClient(path='./qdrant_data', force_disable_check_same_thread=True)
        store.refresh_storage_metrics()
    try:
        with TestClient(main.app) as api:
            if scenario in ('same', 'different'):
                count = 8
                barrier = threading.Barrier(count)
                with ThreadPoolExecutor(max_workers=count) as pool:
                    futures = [pool.submit(upload,api, 'same.pdf' if scenario=='same' else f'{i}.pdf', f'Synthetic upload {i}: blue folders.', 3) for i in range(count)]
                    results = [f.result(timeout=30) for f in futures]
                expected_docs = 1 if scenario=='same' else count
                points = visible()
                assert len(points) == expected_docs * results[0]['total_chunks']
                assert len({p.payload['document_name'] for p in points}) == expected_docs
                if scenario=='same':
                    assert len({p.payload['_doclens_revision'] for p in points}) == 1
                check_counts(expected_docs, len(points))
                restart()
                assert len(visible()) == len(points)
                check_counts(expected_docs, len(points))
            elif scenario in ('partial_write', 'publication_failure', 'retry_restart'):
                upload(api, 'same.pdf', 'Previous searchable wording: blue folders.')
                old = [p.id for p in visible('same.pdf')]
                if scenario == 'publication_failure':
                    failure = patch.object(store, '_publish', side_effect=sqlite3.OperationalError('synthetic catalog failure'))
                else:
                    original = store.client.upsert
                    def partial(*args, **kwargs):
                        kwargs['points'] = kwargs['points'][:1]
                        original(*args, **kwargs)
                        raise RuntimeError('synthetic partial vector write')
                    failure = patch.object(store.client, 'upsert', side_effect=partial)
                with failure:
                    try: upload(api, 'same.pdf', 'Replacement wording: red folders.', 4)
                    except (RuntimeError, sqlite3.OperationalError): pass
                    else: raise AssertionError('Injected storage failure was swallowed')
                assert [p.id for p in visible('same.pdf')] == old
                assert 'blue folders' in store.search_chunks([1.]+[0.]*383,document_name='same.pdf')[0].payload['text']
                assert 'blue folders' in store.search_chunks_bm25('blue',document_name='same.pdf')[0][0].payload['text']
                check_counts(1,1)
                restart()
                assert [p.id for p in visible('same.pdf')] == old
                if scenario=='retry_restart':
                    upload(api, 'same.pdf', 'Replacement wording: red folders.',4)
                    upload(api, 'same.pdf', 'Replacement wording: red folders.',4)
                    restart()
                    assert len(visible('same.pdf')) == 4
                    assert len({p.payload['_doclens_revision'] for p in visible('same.pdf')}) == 1
                    assert all('red folders' in p.payload['text'] for p in visible('same.pdf'))
                    check_counts(1,4)
            elif scenario == 'process_exit':
                upload(api,'same.pdf','Previous committed policy.',2)
                old = sorted(p.id for p in visible())
                store.client.close()
                script = """
import sys, types, os
from unittest.mock import Mock
sys.path.insert(0,sys.argv[1])
sentence=types.ModuleType('sentence_transformers'); sentence.CrossEncoder=Mock()
sys.modules['sentence_transformers']=sentence
import vector_store as store
store.client.upsert(store.COLLECTION_NAME,points=[store.PointStruct(id=str(store.uuid4()),vector=[1.]+[0.]*383,payload={'document_name':'same.pdf','chunk_id':'staged','page_number':1,'text':'Uncommitted revision','_doclens_revision':str(store.uuid4())})],wait=True)
os._exit(23)  # Simulated worker death after durable vector write, before publication.
"""
                process = subprocess.run([sys.executable,'-c',script,str(ROOT/'backend')],capture_output=True,text=True,timeout=20)
                assert process.returncode == 23, process.stderr
                store.client = store.QdrantClient(path='./qdrant_data',force_disable_check_same_thread=True)
                assert sorted(p.id for p in visible()) == old
                check_counts(1,2)
                restart()
            elif scenario == 'new_document_failure':
                original = store.client.upsert
                def partial(*args, **kwargs):
                    kwargs['points'] = kwargs['points'][:1]
                    original(*args, **kwargs)
                    raise RuntimeError('synthetic partial first upload')
                with patch.object(store.client,'upsert',side_effect=partial):
                    try: upload(api,'first.pdf','Incomplete new document.',3)
                    except RuntimeError: pass
                    else: raise AssertionError('Expected storage failure')
                assert not visible()
                check_counts(0,0)
                restart(); assert not visible()
            elif scenario == 'legacy':
                store.create_collection()
                store.client.upsert(store.COLLECTION_NAME, points=[store.PointStruct(id=str(store.uuid4()),vector=[1.]+[0.]*383,payload={'document_name':'legacy.pdf','chunk_id':'old','page_number':1,'text':'Legacy blue wording.'})])
                assert len(visible()) == 1
                upload(api, 'legacy.pdf', 'Published red wording.',2)
                assert len(visible()) == 2
                assert all('red wording' in p.payload['text'] for p in visible())
                check_counts(1,2)
                restart(); assert len(visible()) == 2
            elif scenario == 'dense':
                text = ' '.join(f'Clause {i}: synthetic policy condition and supporting evidence.' for i in range(65))
                # Real text on every page: not file-size padding. 60 pages generate hundreds of chunks.
                result = upload(api, 'dense.pdf', text,60)
                assert result['total_chunks'] >= 180, result
                assert len(visible()) == result['total_chunks']
                check_counts(1,result['total_chunks'])
            elif scenario == 'readers':
                upload(api, 'same.pdf', 'Old complete policy wording.',2)
                entered, release = threading.Event(), threading.Event()
                original = store.client.upsert
                def staged(*args, **kwargs):
                    original(*args, **kwargs)
                    entered.set(); assert release.wait(5)
                    raise RuntimeError('synthetic failure before publication')
                with patch.object(store.client,'upsert',side_effect=staged), ThreadPoolExecutor(max_workers=4) as pool:
                    writer = pool.submit(upload, api,'same.pdf','New incomplete wording.',3)
                    assert entered.wait(5)
                    reader = pool.submit(store.hybrid_search,'policy',[1.]+[0.]*383,3,'same.pdf')
                    assert api.get('/').status_code == 200
                    assert api.get('/metrics').status_code == 200
                    release.set()
                    try: writer.result(timeout=5)
                    except RuntimeError: pass
                    else: raise AssertionError('Expected failure')
                    results = reader.result(timeout=5)
                    assert len(results) == 2
                    assert all('Old complete' in p.payload['text'] for p in results)
            else:
                raise AssertionError(scenario)
        print('PASS real local Qdrant/SQLite HTTP scenario:',scenario)
    finally:
        store.client.close()
