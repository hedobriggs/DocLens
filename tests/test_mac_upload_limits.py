"""Failure/recovery regressions, real PDF parser and real local Qdrant semantics.

Inference and generation are deliberately controlled for deterministic failures;
real-model/server performance is measured separately, not inferred from these tests.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import ModuleType
import unittest
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def pdf(pages=1, text='Synthetic existing contract evidence.'):
    with fitz.open() as document:
        for _ in range(pages):
            page = document.new_page()
            if text: page.insert_text((30, 40), text)
        return document.tobytes()


class UploadLimits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules = {}
        for name in ('embeddings', 'generation', 'sentence_transformers'):
            modules[name] = ModuleType(name)
        modules['embeddings'].create_embedding = lambda text: [1.0]+[0.0]*383
        modules['embeddings'].create_embeddings = lambda texts, check=lambda: None: [[1.0]+[0.0]*383 for _ in texts]
        modules['generation'].generate_answer = lambda **kwargs: {'answer':'synthetic', 'source_ids':[]}
        modules['sentence_transformers'].CrossEncoder = lambda *args, **kwargs: None
        cls.modules = patch.dict(sys.modules, modules); cls.modules.start()
        cls.env = patch.dict(os.environ, {'DOCLENS_SESSION_SECRET':'synthetic-limits-key'});cls.env.start()
        # Avoid a network constructor during import; every test installs its own
        # real temporary Qdrant collection below.
        with patch('qdrant_client.QdrantClient'):
            cls.main = importlib.import_module('main')
            cls.storage = importlib.import_module('vector_store')
        cls.uploads = importlib.import_module('upload_processing')
        cls.publication = importlib.import_module('document_publication')

    @classmethod
    def tearDownClass(cls):
        cls.env.stop();cls.modules.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage.client = QdrantClient(path=self.temp.name, force_disable_check_same_thread=True)
        self.api = TestClient(self.main.app);self.api.__enter__()
        self.headers = {'X-DocLens-Internal-Key':'synthetic-limits-key'}
        self.data = pdf()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.storage.client.close)
        self.addCleanup(lambda:self.api.__exit__(None,None,None))

    def test_hybrid_search_uses_one_revision_when_publication_races_dense_and_bm25(self):
        from types import SimpleNamespace
        vector = [1.0] + [0.0] * 383
        for legacy in (True, False):
            for scoped in (True, False):
                with self.subTest(legacy=legacy, scoped=scoped):
                    # Isolate global searches from earlier subtests too.
                    if self.storage.client.collection_exists(self.storage.COLLECTION_NAME):
                        self.storage.client.delete_collection(self.storage.COLLECTION_NAME)
                    if self.storage.client.collection_exists(self.publication.CATALOG):
                        self.storage.client.delete_collection(self.publication.CATALOG)
                    old = self.old(legacy=legacy)
                    original_query = self.storage.client.query_points
                    parts = [
                        {'text': text, 'metadata': {'document_name': 'existing.pdf',
                            'page_number': 1, 'chunk_id': f'p1-c{i}'}}
                        for i, text in enumerate(('needle replacement evidence', 'unrelated wording', 'different terms'))
                    ]
                    def publish_after_dense(*args, **kwargs):
                        result = original_query(*args, **kwargs)
                        self.storage.replace_document('existing.pdf', parts, [vector] * 3)
                        return result
                    # Exercise real dense search, BM25, fusion and publication;
                    # only reranker scores are controlled (no model download).
                    reranker = SimpleNamespace(predict=lambda pairs: [1.0] * len(pairs))
                    with patch.object(self.storage.client, 'query_points', side_effect=publish_after_dense), \
                         patch.object(self.storage, 'get_reranker', return_value=reranker), \
                         patch.object(sys.modules['embeddings'], 'inference_lock', threading.RLock(), create=True):
                        results = self.storage.hybrid_search('needle', vector, limit=10,
                            document_name='existing.pdf' if scoped else None)
                    self.assertEqual({str(p.id) for p in results}, old)
                    current = {str(p.id) for p in self.visible()}
                    self.assertEqual(len(current), 3)
                    self.assertFalse(current & old)
                    with patch.object(self.storage, 'get_reranker', return_value=reranker), \
                         patch.object(sys.modules['embeddings'], 'inference_lock', threading.RLock(), create=True):
                        subsequent = self.storage.hybrid_search('needle', vector, limit=10,
                            document_name='existing.pdf' if scoped else None)
                    self.assertEqual({str(p.id) for p in subsequent}, current)

    def upload(self, data=None, name='existing.pdf'):
        return self.api.post('/documents/process',headers=self.headers,
            files={'file':(name, self.data if data is None else data,'application/pdf')})

    def visible(self, name='existing.pdf'):
        return self.storage.client.scroll(self.storage.COLLECTION_NAME,
            scroll_filter=self.publication.visible_filter(self.storage.client,name),limit=1000,with_vectors=False)[0]

    def old(self, legacy=False):
        chunk={'text':'Original synthetic evidence', 'metadata':{'document_name':'existing.pdf','page_number':1,'chunk_id':'p1-c1'}}
        vector=[1.0]+[0.0]*383
        chunks=[chunk]+[{'text':'Secondary unrelated wording', 'metadata':{**chunk['metadata'],'chunk_id':f'p1-c{i}'}} for i in (2,3)]
        if legacy:
            self.storage.create_collection()
            self.storage.client.upsert(self.storage.COLLECTION_NAME,points=[PointStruct(id=str(uuid4()),vector=vector,payload={'text':part['text'],**part['metadata']}) for part in chunks],wait=True)
        else:self.storage.replace_document('existing.pdf',chunks,[vector]*len(chunks))
        return {str(p.id) for p in self.visible()}

    def test_health_and_metrics_responsive_and_second_upload_rejected_while_embedding_busy(self):
        started=threading.Event();release=threading.Event()
        def busy(texts,check):
            started.set();release.wait(5);check();return [[1.0]+[0.0]*383 for _ in texts]
        with patch('embeddings.create_embeddings',side_effect=busy), ThreadPoolExecutor() as pool:
            future=pool.submit(self.upload)
            try:
                self.assertTrue(started.wait(2))
                for path in ('/','/metrics'):
                    begin=time.monotonic()
                    self.assertEqual(pool.submit(self.api.get,path).result(timeout=.75).status_code,200)
                    self.assertLess(time.monotonic()-begin,.75)
                self.assertEqual(self.upload().status_code,429)
            finally:release.set()
            self.assertEqual(future.result(timeout=5).status_code,200)

    def test_limits_and_scans_leave_old_revision_unchanged(self):
        old=self.old()
        cases=[('MAX_PAGES',1,pdf(2)),('MAX_TEXT',5,pdf()),('MAX_PAGE_TEXT',5,pdf()),('MAX_CHUNKS',1,pdf(2))]
        for limit,value,data in cases:
            with self.subTest(limit=limit),patch.object(self.uploads,limit,value):
                self.assertEqual(self.upload(data).status_code,413)
                self.assertEqual({str(p.id) for p in self.visible()},old)
        self.assertEqual(self.upload(pdf(text='')).status_code,400)
        self.assertEqual(self.upload(b'broken PDF').status_code,400)
        self.assertEqual({str(p.id) for p in self.visible()},old)

    def test_embedding_failure_preserves_existing_points_and_hides_exception_text(self):
        old=self.old(legacy=True)
        with patch('embeddings.create_embeddings',side_effect=RuntimeError('sensitive-value-must-not-appear')):
            with self.assertLogs('doclens',level='WARNING') as logs:response=self.upload()
        self.assertEqual(response.status_code,503)
        self.assertNotIn('sensitive-value',response.text+' '.join(logs.output))
        self.assertIn('RuntimeError',' '.join(logs.output))
        self.assertEqual({str(p.id) for p in self.visible()},old)

    def test_timeout_holds_admission_until_worker_exits_and_never_publishes(self):
        old=self.old();started=threading.Event();release=threading.Event()
        def busy(texts,check):
            started.set();release.wait(4);check();return [[1.0]+[0.0]*383 for _ in texts]
        with patch.object(self.uploads,'PROCESSING_SECONDS',.15),patch('embeddings.create_embeddings',side_effect=busy):
            try:
                response=self.upload();self.assertTrue(started.is_set())
                self.assertEqual(response.status_code,504)
                self.assertEqual(self.upload().status_code,429)
                self.assertEqual({str(p.id) for p in self.visible()},old)
            finally:release.set()
            deadline=time.monotonic()+3
            while not self.uploads._admission.acquire(blocking=False):
                self.assertLess(time.monotonic(),deadline);time.sleep(.01)
            self.uploads._admission.release()
        self.assertEqual(self.upload().status_code,200)

    def test_partial_batch_and_pointer_failure_preserve_all_read_paths(self):
        for legacy in (True,False):
            with self.subTest(legacy=legacy):
                old=self.old(legacy=legacy)
                chunks=[{'text':'Replacement hidden wording', 'metadata':{'document_name':'existing.pdf','page_number':2,'chunk_id':f'p2-c{i}'}} for i in range(205)]
                vectors=[[1.0]+[0.0]*383 for _ in chunks]
                upsert=self.storage.client.upsert;count=0
                def fail_second(collection_name,*args,**kwargs):
                    nonlocal count
                    if collection_name==self.storage.COLLECTION_NAME:
                        count+=1
                        if count==2:raise ConnectionError('synthetic batch outage')
                    return upsert(collection_name,*args,**kwargs)
                with patch.object(self.storage.client,'upsert',side_effect=fail_second):
                    with self.assertRaises(ConnectionError):self.storage.replace_document('existing.pdf',chunks,vectors)
                self.assertEqual({str(p.id) for p in self.visible()},old)
                self.assertEqual({str(p.id) for p in self.storage.search_chunks(vectors[0],10,'existing.pdf')},old)
                self.assertEqual({str(p.id) for p in self.storage.search_chunks_bm25('Original',10,'existing.pdf')},{str(p.id) for p in self.visible() if 'Original' in p.payload['text']})
                self.assertEqual(self.storage.list_documents(),[{'name':'existing.pdf','status':'Ready','chunks':len(old)}])
                def fail_pointer(collection_name,*args,**kwargs):
                    if collection_name==self.publication.CATALOG:raise ConnectionError('synthetic pointer outage')
                    return upsert(collection_name,*args,**kwargs)
                with patch.object(self.storage.client,'upsert',side_effect=fail_pointer):
                    with self.assertRaises(ConnectionError):self.storage.replace_document('existing.pdf',chunks[:1],vectors[:1])
                self.assertEqual({str(p.id) for p in self.visible()},old)
                self.storage.replace_document('existing.pdf',chunks[:1],vectors[:1])
                self.assertEqual(len(self.visible()),1)
                self.assertTrue(all(p.payload['text']=='Replacement hidden wording' for p in self.visible()))
                raw=self.storage.client.retrieve(self.storage.COLLECTION_NAME,ids=list(old),with_payload=True)
                self.assertEqual(len(raw),len(old))

    def test_catalog_survives_reopen_and_existing_citation_metadata_is_preserved(self):
        old=self.old()
        self.storage.client.close()
        self.storage.client=QdrantClient(path=self.temp.name,force_disable_check_same_thread=True)
        self.assertEqual({str(p.id) for p in self.visible()},old)
        self.assertEqual({p.payload['chunk_id'] for p in self.visible()},{'p1-c1','p1-c2','p1-c3'})
        self.addCleanup(self.storage.client.close)

    def test_staging_cancellation_keeps_old_publication(self):
        old=self.old();calls=0
        def check():
            nonlocal calls
            calls+=1
            if calls>=3:raise TimeoutError('synthetic cancellation')
        chunks=[{'text':'hidden', 'metadata':{'document_name':'existing.pdf','page_number':2,'chunk_id':f'p2-c{i}'}} for i in range(205)]
        with self.assertRaises(TimeoutError):self.storage.replace_document('existing.pdf',chunks,[[1.0]+[0.0]*383 for _ in chunks],check=check)
        self.assertEqual({str(p.id) for p in self.visible()},old)

    def test_auth_declared_size_chunked_size_and_body_deadline_before_parsing(self):
        async def run(headers, messages):
            reads=0;sent=[]
            async def receive():
                nonlocal reads
                reads+=1
                if messages:
                    return messages.pop(0)
                await asyncio.sleep(1)
                return {'type':'http.disconnect'}
            async def send(message):sent.append(message)
            scope={'type':'http','method':'POST','path':'/documents/process','headers':headers}
            async def downstream(*args):raise AssertionError('Oversized/unauthorized body reached parser')
            await self.uploads.UploadGate(downstream)(scope,receive,send)
            return sent[0]['status'],reads
        status,reads=asyncio.run(run([],[]));self.assertEqual((status,reads),(401,0))
        auth=[(b'x-doclens-internal-key',b'synthetic-limits-key')]
        status,reads=asyncio.run(run(auth+[(b'content-length',b'999999999')],[]));self.assertEqual((status,reads),(413,0))
        with patch.object(self.uploads,'MAX_BODY_BYTES',1024):
            status,reads=asyncio.run(run(auth,[{'type':'http.request','body':b'x'*1025,'more_body':True}]))
            self.assertEqual((status,reads),(413,1))
        with patch.object(self.uploads,'BODY_SECONDS',.01):
            status,reads=asyncio.run(run(auth,[]));self.assertEqual(status,408)
        self.assertEqual(self.upload().status_code,200)

    def test_openapi_preserves_multipart_upload_and_required_auth_header(self):
        schema=self.api.get('/openapi.json').json()
        for path in ('/documents/process','/documents/extract'):
            operation=schema['paths'][path]['post']
            body=operation['requestBody']['content']['multipart/form-data']['schema']
            self.assertEqual(body['properties']['file']['format'],'binary')
            self.assertEqual(body['required'],['file'])
            self.assertTrue(any(p['in']=='header' and p['name']=='X-DocLens-Internal-Key' and p['required'] for p in operation['parameters']))

    def test_exact_file_byte_limit_and_one_byte_over_preserve_index(self):
        with patch.object(self.uploads,'MAX_FILE_BYTES',len(self.data)):
            self.assertEqual(self.upload().status_code,200)
            old={str(p.id) for p in self.visible()}
            self.assertEqual(self.upload(self.data+b' ').status_code,413)
            self.assertEqual({str(p.id) for p in self.visible()},old)

    def test_lost_publication_acknowledgement_retains_old_and_only_complete_new_revision(self):
        old=self.old()
        chunks=[{'text':'Complete new evidence', 'metadata':{'document_name':'existing.pdf','page_number':2,'chunk_id':f'p2-c{i}'}} for i in (1,2)]
        original=self.storage.client.upsert
        def lose_ack(collection,*args,**kwargs):
            result=original(collection,*args,**kwargs)
            if collection==self.publication.CATALOG:raise ConnectionError('synthetic acknowledgement loss after commit')
            return result
        with patch.object(self.storage.client,'upsert',side_effect=lose_ack):
            with self.assertRaises(ConnectionError):self.storage.replace_document('existing.pdf',chunks,[[1.0]+[0.0]*383]*2)
        self.assertEqual(len(self.visible()),2)
        self.assertTrue(all(p.payload['text']=='Complete new evidence' for p in self.visible()))
        self.assertEqual(len(self.storage.client.retrieve(self.storage.COLLECTION_NAME,ids=list(old))),len(old))

    def test_disconnect_stops_work_before_publication(self):
        import requests
        old=self.old();started=threading.Event();release=threading.Event()
        def busy(texts,check):
            started.set();release.wait(3);check();return [[1.0]+[0.0]*383 for _ in texts]
        prepared=requests.Request('POST','http://testserver/documents/process',headers=self.headers,
            files={'file':('existing.pdf',self.data,'application/pdf')}).prepare()
        async def run():
            sent=[];received=False
            async def receive():
                nonlocal received
                if not received:
                    received=True
                    return {'type':'http.request','body':prepared.body,'more_body':False}
                if started.is_set():return {'type':'http.disconnect'}
                await asyncio.sleep(1)
                return {'type':'http.disconnect'}
            async def send(message):sent.append(message)
            scope={'type':'http','http_version':'1.1','method':'POST','scheme':'http',
                'path':'/documents/process','raw_path':b'/documents/process','query_string':b'',
                'root_path':'','server':('testserver',80),'client':('127.0.0.1',1),
                'headers':[(k.lower().encode(),v.encode()) for k,v in prepared.headers.items()]}
            await self.main.app(scope,receive,send)
            return sent
        with patch('embeddings.create_embeddings',side_effect=busy):
            try:
                result=asyncio.run(run());self.assertTrue(started.is_set())
                self.assertEqual(result[0]['status'],499)
            finally:release.set()
            deadline=time.monotonic()+3
            while not self.uploads._admission.acquire(blocking=False):
                self.assertLess(time.monotonic(),deadline);time.sleep(.01)
            self.uploads._admission.release()
        self.assertEqual({str(p.id) for p in self.visible()},old)


if __name__=='__main__':unittest.main(verbosity=2)
