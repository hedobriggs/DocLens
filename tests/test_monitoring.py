import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MonitoringTests(unittest.TestCase):
    def test_provisioned_dashboards_and_datasources(self):
        files = [ROOT/'monitoring/grafana/doclens.json', *sorted((ROOT/'monitoring/grafana/dashboards').glob('*.json'))]
        dashboards = [json.loads(p.read_text()) for p in files]
        self.assertEqual({d['uid'] for d in dashboards}, {'doclens', 'doclens-system', 'doclens-ai', 'doclens-application', 'doclens-storage'})
        for d in dashboards:
            for p in d['panels']:
                self.assertEqual(p['datasource']['uid'], 'prometheus')
                self.assertTrue(p['targets'][0]['expr'])
                self.assertNotIn('vector(0)', p['targets'][0]['expr'])
        overview = dashboards[0]
        self.assertTrue({'/d/doclens-system','/d/doclens-ai','/d/doclens-application','/d/doclens-storage'}.issubset({link['url'] for link in overview['links']}))

    def test_real_instrumentation_with_isolated_model_provider(self):
        script = r'''
import os, sys, tempfile, types
from unittest.mock import Mock, patch
sys.path.insert(0, str(__import__('pathlib').Path('backend').resolve()))
from prometheus_client import generate_latest
from observability import measure
# Isolate heavyweight inference, retain actual embedding/reranking wrappers and Qdrant.
sentence = types.ModuleType('sentence_transformers')
model = Mock(); model.encode.return_value = __import__('numpy').array([1.] + [0.]*383)
sentence.SentenceTransformer = Mock(return_value=model)
reranker = Mock(); reranker.predict.return_value = [1.]
sentence.CrossEncoder = Mock(return_value=reranker)
with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'sentence_transformers': sentence}):
    os.chdir(tmp)
    import embeddings, vector_store, generation
    embedding = embeddings.create_embedding('Blue folders')
    vector_store.create_collection()
    vector_store.store_chunks([{'text':'Blue folders','metadata':{'document_name':'test.pdf','page_number':1,'chunk_id':'p1'}}],[embedding])
    results = vector_store.hybrid_search('folder color', embedding)
    response = types.SimpleNamespace(text='{"answer":"Blue", "source_ids":[1]}', usage_metadata=types.SimpleNamespace(prompt_token_count=100, candidates_token_count=10))
    generation.client = Mock(); generation.client.models.generate_content.return_value=response
    with patch.dict(os.environ, {'GEMINI_INPUT_USD_PER_MILLION':'1','GEMINI_OUTPUT_USD_PER_MILLION':'2'}):
        assert generation.generate_answer('color?', results)['answer'] == 'Blue'
    generation.client.models.generate_content.side_effect=RuntimeError('provider unavailable')
    try: generation.generate_answer('color?', results)
    except RuntimeError: pass
    else: raise AssertionError('Provider failure was swallowed')
    text = generate_latest().decode()
    for expected in ['operation="embedding"','operation="reranking"','operation="gemini"','outcome="error"','doclens_documents{collection="document_chunks"} 1.0','doclens_chunks{collection="document_chunks"} 1.0','doclens_qdrant_storage_bytes','direction="input"','direction="output"','doclens_gemini_estimated_cost_usd_total{currency="USD"}']:
        assert expected in text, expected
    vector_store.delete_document('test.pdf')
    assert 'doclens_documents{collection="document_chunks"} 0.0' in generate_latest().decode()
    vector_store.client.close()
print('Instrumented embedding, reranking, Gemini success/error/usage/cost and storage passed')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == '__main__':
    unittest.main()
