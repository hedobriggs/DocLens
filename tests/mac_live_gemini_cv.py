"""Opt-in live Gemini evaluation: synthetic PDF, local Qdrant, controlled embeddings.

Uses GEMINI_API_KEY or the environment's existing GERMINI_API_KEY binding.
Never prints credentials/provider exceptions; no customer files are accepted.
"""
import json
import logging
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from google import genai
from test_mac_document_coverage import Coverage, EMPLOYERS


def main():
    logging.disable(logging.CRITICAL)  # Provider exceptions may include request metadata.
    key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GERMINI_API_KEY')
    if not key:
        raise SystemExit('Missing configured Gemini credential; no request made')
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=False)
    results = {'application_commit':'66db29f0b072fd9821869f4ffef008883ce0509b',
               'provider':'live Gemini', 'model':'gemini-3.5-flash-lite',
               'fixture':'seven-page synthetic CV; five employers; two distractor pages',
               'inference':'controlled embeddings; real PDF ingestion and local Qdrant',
               'expected_employers':EMPLOYERS, 'attempts':[]}
    Coverage.setUpClass()
    case = Coverage('test_coverage_all_five_with_original_citations_and_real_prompt')
    try:
        case.setUp()
        points = case.seed_cv()
        expected = [{k:p.payload[k] for k in ('document_name','page_number','chunk_id')}
                    for p in points if 'Employer:' in p.payload['text']]
        results['expected_citations'] = expected
        live = genai.Client(api_key=key, http_options={'timeout':60000})
        case.generation.client = live
        # Preserve the reviewed prompt/parser. Only replace the stub used by the
        # deterministic upload suite with real generation and a live client.
        for attempt in range(1, 4):
            started = time.monotonic()
            record = {'attempt':attempt}
            try:
                with patch.object(case.main, 'generate_answer', case.generation.generate_answer):
                    response = case.api.post('/ask', headers=case.headers, json={
                        'question':'List all employers in this CV', 'document_name':'synthetic-cv.pdf'})
                body = response.json()
                record.update(status=response.status_code, response=body)
                record['all_five_present'] = all(name in body.get('answer','') for name in EMPLOYERS)
                record['correct_citations'] = (sorted(body.get('citations',[]),key=lambda c:c['page_number'])
                                                == sorted(expected,key=lambda c:c['page_number']))
                record['passed'] = response.status_code==200 and record['all_five_present'] and record['correct_citations']
            except Exception as exc:
                record.update(passed=False, exception_class=type(exc).__name__)
            record['seconds'] = round(time.monotonic()-started,3)
            results['attempts'].append(record)
            (destination/'results.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps({k:v for k,v in record.items() if k!='response'}),flush=True)
        live.close()
    finally:
        case.doCleanups()
        Coverage.tearDownClass()
    raise SystemExit(not all(a['passed'] for a in results['attempts']))


if __name__ == '__main__':
    main()
