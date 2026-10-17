"""Real-server failure publication checks, no inference/provider or customer data."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from document_publication import replace, visible_filter, ensure_collection, CATALOG
from qdrant_client.models import Distance
from mac_upload_recovery_smoke import docker, ready

COLLECTION='document_chunks'
VECTOR=[1.0]+[0.0]*383


def chunks(name,count,text='Complete synthetic evidence'):
    return [{'text':text,'metadata':{'document_name':name,'page_number':1,'chunk_id':f'p1-c{i}'}} for i in range(count)]


class PublicationServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name='doclens-publication-test-'+uuid4().hex[:8]
        docker('run','-d','--name',cls.name,'-p','127.0.0.1::6333','qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863')
        cls.url='http://127.0.0.1:'+docker('port',cls.name,'6333').rsplit(':',1)[1]
        ready(cls.url+'/readyz')

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['docker','rm','-f','-v',cls.name],check=True,stdout=subprocess.DEVNULL)

    def setUp(self):
        self.client=QdrantClient(url=self.url,timeout=5,trust_env=False)
        self.addCleanup(self.client.close)
        self.document=uuid4().hex+'.pdf'

    def ids(self):
        return {str(p.id) for p in self.client.scroll(COLLECTION,scroll_filter=visible_filter(self.client,self.document),limit=1000)[0]}

    def old(self,legacy):
        parts=chunks(self.document,3,'Original synthetic text')
        if legacy:
            ensure_collection(self.client,COLLECTION,384,Distance.COSINE)
            self.client.upsert(COLLECTION,points=[PointStruct(id=str(uuid4()),vector=VECTOR,payload={'text':c['text'],**c['metadata']}) for c in parts],wait=True)
        else:replace(self.client,COLLECTION,self.document,parts,[VECTOR]*3)
        return self.ids()

    def test_partial_batch_and_failed_pointer_leave_exact_existing_view(self):
        for legacy in (True,False):
            with self.subTest(legacy=legacy):
                self.document=uuid4().hex+'.pdf';old=self.old(legacy);parts=chunks(self.document,205)
                original=self.client.upsert;calls=0
                def fail_second(collection,*args,**kwargs):
                    nonlocal calls
                    if collection==COLLECTION:
                        calls+=1
                        if calls==2:raise ConnectionError('synthetic server batch failure')
                    return original(collection,*args,**kwargs)
                with patch.object(self.client,'upsert',side_effect=fail_second):
                    with self.assertRaises(ConnectionError):replace(self.client,COLLECTION,self.document,parts,[VECTOR]*len(parts))
                self.assertEqual(self.ids(),old)
                self.assertEqual({str(p.id) for p in self.client.query_points(COLLECTION,query=VECTOR,
                    query_filter=visible_filter(self.client,self.document),limit=10).points},old)
                def fail_pointer(collection,*args,**kwargs):
                    if collection==CATALOG:raise ConnectionError('synthetic server pointer failure')
                    return original(collection,*args,**kwargs)
                with patch.object(self.client,'upsert',side_effect=fail_pointer):
                    with self.assertRaises(ConnectionError):replace(self.client,COLLECTION,self.document,parts[:1],[VECTOR])
                self.assertEqual(self.ids(),old)
                self.assertEqual(len(self.client.retrieve(COLLECTION,ids=list(old))),3)

    def test_lost_ack_and_reconnected_reader_see_complete_revision_and_retain_old_points(self):
        old=self.old(False);parts=chunks(self.document,2);original=self.client.upsert
        def lose_ack(collection,*args,**kwargs):
            result=original(collection,*args,**kwargs)
            if collection==CATALOG:raise ConnectionError('synthetic lost server acknowledgement')
            return result
        with patch.object(self.client,'upsert',side_effect=lose_ack):
            with self.assertRaises(ConnectionError):replace(self.client,COLLECTION,self.document,parts,[VECTOR]*2)
        new=self.ids();self.assertEqual(len(new),2);self.assertFalse(new&old)
        self.assertEqual(len(self.client.retrieve(COLLECTION,ids=list(old))),3)
        reconnected=QdrantClient(url=self.url,timeout=5,trust_env=False)
        try:
            points=reconnected.scroll(COLLECTION,scroll_filter=visible_filter(reconnected,self.document),limit=100)[0]
            self.assertEqual({str(p.id) for p in points},new)
        finally:reconnected.close()


class SearchRaceServer(unittest.TestCase):
    """Reuse the deterministic race against HTTP Qdrant, not only local storage."""
    @classmethod
    def setUpClass(cls):
        from test_mac_upload_limits import UploadLimits
        cls.fixture = UploadLimits
        UploadLimits.setUpClass.__func__(cls)
        try:
            PublicationServer.setUpClass.__func__(cls)
        except BaseException:
            UploadLimits.tearDownClass.__func__(cls)
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            PublicationServer.tearDownClass.__func__(cls)
        finally:
            cls.fixture.tearDownClass.__func__(cls)

    def setUp(self):
        self.storage.client = QdrantClient(url=self.url, timeout=5, trust_env=False)
        self.addCleanup(self.storage.client.close)

    def old(self, legacy=False):
        return self.fixture.old(self, legacy)

    def visible(self, name='existing.pdf'):
        return self.fixture.visible(self, name)

    def test_hybrid_search_revision_race(self):
        self.fixture.test_hybrid_search_uses_one_revision_when_publication_races_dense_and_bm25(self)


if __name__=='__main__':unittest.main(verbosity=2)
