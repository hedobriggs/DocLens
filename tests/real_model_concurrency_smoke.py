"""Opt-in real-model/real-storage test. Requires the documented cached models.

No Gemini request, no confidential data, no padded PDFs; not part of mocked CI.
"""
import os
from pathlib import Path
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import fitz
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory(prefix='doclens-real-model-') as tmp:
    os.chdir(tmp)
    os.environ['DOCLENS_SESSION_SECRET']='synthetic-local-model-test-only-key'
    import main
    import vector_store as store
    barrier=threading.Barrier(4)
    def upload(api,name,marker):
        with fitz.open() as document:
            for page in range(10):
                text=' '.join(f'Clause {i}: {marker} synthetic property wording and supporting evidence.' for i in range(25))
                result=document.new_page().insert_textbox((36,36,560,800),text)
                assert result >= 0, 'Dense fixture did not fit on page'
            data=document.tobytes()
        barrier.wait(10)
        response=api.post('/documents/process',headers={'X-DocLens-Internal-Key':os.environ['DOCLENS_SESSION_SECRET']},files={'file':(name,data,'application/pdf')})
        assert response.status_code==200,response.text
        assert response.json()['total_chunks']>=20,response.text
        return response.json()
    try:
        with TestClient(main.app) as api, ThreadPoolExecutor(max_workers=4) as pool:
            jobs=[pool.submit(upload,api,name,marker) for name,marker in [('same.pdf','blue'),('same.pdf','red'),('a.pdf','green'),('b.pdf','yellow')]]
            completed=[job.result(timeout=120) for job in jobs]
        points,_=store.client.scroll(store.COLLECTION_NAME,scroll_filter=store._visible_filter(),limit=10000)
        assert len({p.payload['document_name'] for p in points})==3
        assert len({p.payload['_doclens_revision'] for p in points if p.payload['document_name']=='same.pdf'})==1
        expected=completed[2]['total_chunks']+completed[3]['total_chunks']+completed[0]['total_chunks']
        assert len(points)==expected,(len(points),expected)
        from embeddings import create_embedding
        results=store.hybrid_search('What is the property wording?',create_embedding('What is the property wording?'),3,'same.pdf')
        assert results and all(p.payload['document_name']=='same.pdf' for p in results)
        print('PASS four simultaneous genuine 10-page PDF uploads; real embedding/reranking models, Qdrant and SQLite; 3 documents,',len(points),'active chunks; same-document publication is complete')
    finally:
        store.client.close()
