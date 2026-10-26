"""Synthetic CV, real PDF ingestion/local Qdrant; controlled Gemini response."""
import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from test_mac_upload_limits import UploadLimits, ROOT
import fitz

EMPLOYERS = ['Aster Research', 'Birch Analytics', 'Cobalt Systems', 'Delta Robotics', 'Elm Computing']


class Coverage(UploadLimits):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Load the actual prompt/response implementation rather than the base
        # upload suite's generation stub. No external provider request is made.
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-not-a-real-key'}):
            spec = importlib.util.spec_from_file_location('coverage_generation', ROOT/'backend/generation.py')
            cls.generation = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.generation)

    def seed_cv(self):
        texts = ['Employer: '+EMPLOYERS[0], 'Employer: '+EMPLOYERS[1],
                 'Skills: Python, analysis and testing.',
                 *['Employer: '+name for name in EMPLOYERS[2:]],
                 'Education: synthetic university.']
        with fitz.open() as doc:
            for text in texts:
                doc.new_page().insert_text((30,40), text)
            data = doc.tobytes()
        response = self.api.post('/documents/process', headers=self.headers,
                                 files={'file': ('synthetic-cv.pdf', data, 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.text)
        return self.storage.complete_document_context('synthetic-cv.pdf')

    def test_coverage_all_five_with_original_citations_and_real_prompt(self):
        points = self.seed_cv()
        self.assertEqual(len(points), 7)
        first_three = '\n'.join(p.payload['text'] for p in points[:3])
        self.assertEqual(sum(name in first_three for name in EMPLOYERS), 2,
                         'Reproduce omission: three passages leave out three employers')
        expected = [i for i,p in enumerate(points, 1) if 'Employer:' in p.payload['text']]
        def provider(**kwargs):
            prompt = kwargs['contents']
            for employer in EMPLOYERS:
                self.assertIn(employer, prompt)
            self.assertIn('Read EVERY supplied source', prompt)
            return SimpleNamespace(text=json.dumps({'answer': '; '.join(EMPLOYERS),
                                                      'source_ids': expected}))
        with patch.object(self.generation.client.models, 'generate_content', side_effect=provider), \
             patch.object(self.main, 'generate_answer', self.generation.generate_answer), \
             patch.object(self.main, 'create_embedding', side_effect=AssertionError('No ranking for exhaustive requests')):
            r = self.api.post('/ask', headers=self.headers, json={
                'question': 'List all employers in this CV', 'document_name': 'synthetic-cv.pdf'})
        self.assertEqual(r.status_code, 200, r.text)
        for employer in EMPLOYERS:
            self.assertIn(employer, r.json()['answer'])
        self.assertEqual(r.json()['citations'], [
            {key: points[i-1].payload[key] for key in ('document_name','page_number','chunk_id')}
            for i in expected])

    def test_coverage_requires_scope_and_never_generates_truncated_answers(self):
        self.seed_cv()
        with patch.object(self.main, 'generate_answer', side_effect=AssertionError('Must not generate')):
            r = self.api.post('/ask', headers=self.headers, json={'question':'List all employers'})
            self.assertEqual(r.status_code, 422)
            with patch('document_coverage.MAX_COVERAGE_CHARACTERS', 10):
                r = self.api.post('/ask', headers=self.headers, json={
                    'question':'List all employers', 'document_name':'synthetic-cv.pdf'})
                self.assertEqual(r.status_code, 422)
                self.assertIn('no partial list', r.json()['detail'])
            with patch('document_coverage.MAX_COVERAGE_CHUNKS', 2):
                r = self.api.post('/ask', headers=self.headers, json={
                    'question':'List all employers', 'document_name':'synthetic-cv.pdf'})
                self.assertEqual(r.status_code, 422)

    def test_coverage_counting_and_listing_questions_receive_every_employer(self):
        points = self.seed_cv()
        questions = [
            'how many organizations has Taylor worked in?',
            'List the number of organizations Taylor has worked in according to the attached CV',
            'What is the total number of employers?',
            'Count the companies in this employment history',
            'List employers in this CV',
        ]
        expected = [i for i,p in enumerate(points, 1) if 'Employer:' in p.payload['text']]
        def provider(**kwargs):
            prompt = kwargs['contents']
            for employer in EMPLOYERS:
                self.assertIn(employer, prompt)
            self.assertIn('report the total alongside their names', prompt)
            return SimpleNamespace(text=json.dumps({
                'answer': '5 employers: ' + '; '.join(EMPLOYERS), 'source_ids': expected}))
        with patch.object(self.generation.client.models, 'generate_content', side_effect=provider), \
             patch.object(self.main, 'generate_answer', self.generation.generate_answer), \
             patch.object(self.main, 'hybrid_search', side_effect=AssertionError('Must not count a ranked subset')):
            for question in questions:
                with self.subTest(question=question):
                    response = self.api.post('/ask', headers=self.headers, json={
                        'question': question, 'document_name': 'synthetic-cv.pdf'})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertTrue(response.json()['answer'].startswith('5 employers:'))
                    self.assertEqual(response.json()['citations'], [
                        {key: points[i-1].payload[key] for key in ('document_name','page_number','chunk_id')}
                        for i in expected])
    def test_coverage_pagination_and_publication_race_preserve_snapshot(self):
        self.seed_cv()
        original = self.storage.client.scroll
        calls = []
        def scroll(**kwargs):
            kwargs['limit'] = 2
            batch, offset = original(**kwargs)
            calls.append(kwargs['scroll_filter'])
            if len(calls) == 1:
                chunks = [{'text':'Employer: Other Revision', 'metadata': {
                    'document_name':'synthetic-cv.pdf','page_number':1,'chunk_id':0}}]
                self.publication.replace(self.storage.client, self.storage.COLLECTION_NAME,
                                         'synthetic-cv.pdf',chunks,[[1.0]+[0.0]*383])
            return batch, offset
        with patch.object(self.storage.client, 'scroll', side_effect=scroll):
            result = self.storage.complete_document_context('synthetic-cv.pdf')
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(f == calls[0] for f in calls))
        text = '\n'.join(p.payload['text'] for p in result)
        for name in EMPLOYERS:
            self.assertIn(name, text)
        self.assertNotIn('Other Revision', text)

    def test_coverage_excludes_other_documents_and_rejects_missing_payload(self):
        self.seed_cv()
        self.publication.replace(self.storage.client, self.storage.COLLECTION_NAME,
            'other.pdf', [{'text':'Unrelated private employer', 'metadata': {
                'document_name':'other.pdf','page_number':1,'chunk_id':'p1-c1'}}],
            [[1.0]+[0.0]*383])
        selected = self.storage.complete_document_context('synthetic-cv.pdf')
        self.assertEqual(len(selected), 7)
        self.assertTrue(all(p.payload['document_name']=='synthetic-cv.pdf' for p in selected))
        from document_coverage import CoverageUnavailable
        self.storage.client.delete_payload(self.storage.COLLECTION_NAME,
                                          keys=['page_number'], points=[selected[0].id])
        with self.assertRaises(CoverageUnavailable):
            self.storage.complete_document_context('synthetic-cv.pdf')

    def test_coverage_explicit_mode_and_normal_search_unchanged(self):
        points = self.seed_cv()
        with patch.object(self.main, 'hybrid_search', return_value=points[:3]) as ranked, \
             patch.object(self.main, 'generate_answer', return_value={'answer':'synthetic','source_ids':[1]}):
            r = self.api.post('/ask', headers=self.headers, json={
                'question':'What is the first role?', 'document_name':'synthetic-cv.pdf'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(ranked.call_args.kwargs['limit'], 3)
            ranked.reset_mock()
            r = self.api.post('/ask', headers=self.headers, json={
                'question':'Enumerate employers', 'document_name':'synthetic-cv.pdf', 'comprehensive':True})
            self.assertEqual(r.status_code, 200)
            ranked.assert_not_called()


if __name__ == '__main__':
    suite = unittest.TestSuite(Coverage(name) for name in unittest.defaultTestLoader.getTestCaseNames(Coverage)
                               if name.startswith('test_coverage_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
