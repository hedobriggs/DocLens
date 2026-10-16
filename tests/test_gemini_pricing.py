"""Real answer/metric code, isolated provider response; no live Gemini calls."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import os, sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,'backend')
from prometheus_client import REGISTRY, generate_latest
import generation
mode=sys.argv[1]
pairs={
 'provider_error_log':(None,None), 'absent':(None,None), 'incomplete':('1',None), 'malformed':('broken','2'),
 'negative':('-1','2'), 'negative_output':('1','-2'), 'nan':('nan','2'),
 'infinity':('1','inf'), 'negative_infinity':('-inf','2'),
 'empty':('','2'), 'valid':('1','2'), 'zero':('0','0'),
 'overflow':('1e308','1e308'),
}
for key,value in zip(('GEMINI_INPUT_USD_PER_MILLION','GEMINI_OUTPUT_USD_PER_MILLION'),pairs[mode]):
    os.environ.pop(key,None)
    if value is not None: os.environ[key]=value
usage=SimpleNamespace(prompt_token_count=100,candidates_token_count=10)
if mode=='overflow': usage=SimpleNamespace(prompt_token_count=10_000_000,candidates_token_count=10_000_000)
generation.client=Mock()
generation.client.models.generate_content.return_value=SimpleNamespace(text='{"answer":"Supported synthetic answer", "source_ids":[1]}',usage_metadata=usage)
chunk=SimpleNamespace(payload={'document_name':'synthetic.pdf','page_number':1,'text':'Synthetic evidence.'})
if mode=='provider_error_log':
    import io, logging
    stream=io.StringIO(); handler=logging.StreamHandler(stream)
    logging.getLogger('doclens').addHandler(handler)
    generation.client.models.generate_content.side_effect=RuntimeError('SENSITIVE_DOCUMENT_TEXT')
    try: generation.generate_answer('SENSITIVE_QUESTION',[chunk])
    except RuntimeError as error:
        assert error.__suppress_context__
        assert 'SENSITIVE' not in str(error)
    else: raise AssertionError('Provider failure was swallowed')
    assert 'SENSITIVE' not in stream.getvalue()
    assert REGISTRY.get_sample_value('doclens_operations_total',{'operation':'gemini','outcome':'error'})==1
    print('PASS provider failure log privacy'); sys.exit(0)
answer=generation.generate_answer('Question?',[chunk])
assert answer=={'answer':'Supported synthetic answer','source_ids':[1]}, answer
assert REGISTRY.get_sample_value('doclens_gemini_tokens_total',{'direction':'input'})==usage.prompt_token_count
assert REGISTRY.get_sample_value('doclens_gemini_tokens_total',{'direction':'output'})==usage.candidates_token_count
assert REGISTRY.get_sample_value('doclens_operations_total',{'operation':'gemini','outcome':'success'})==1
assert REGISTRY.get_sample_value('doclens_operations_total',{'operation':'gemini','outcome':'error'}) is None
cost=REGISTRY.get_sample_value('doclens_gemini_estimated_cost_usd_total',{'currency':'USD'})
if mode in ('valid','zero'):
    assert abs(cost-(0.00012 if mode=='valid' else 0)) < 1e-12, cost
else:
    assert cost is None, cost
    reason={'absent':'not_configured','incomplete':'incomplete','overflow':'overflow'}.get(mode,'invalid')
    assert REGISTRY.get_sample_value('doclens_gemini_cost_estimate_skipped_total',{'reason':reason})==1
print('PASS answer, tokens, operation and cost metrics:', mode)
'''

class GeminiPricingTests(unittest.TestCase):
    def run_case(self, name):
        environment = dict(os.environ)
        environment.pop('GEMINI_API_KEY', None)
        result = subprocess.run([sys.executable, '-c', SCRIPT, name], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absent(self): self.run_case('absent')
    def test_incomplete(self): self.run_case('incomplete')
    def test_malformed(self): self.run_case('malformed')
    def test_empty(self): self.run_case('empty')
    def test_negative_input(self): self.run_case('negative')
    def test_negative_output(self): self.run_case('negative_output')
    def test_nan(self): self.run_case('nan')
    def test_positive_infinity(self): self.run_case('infinity')
    def test_negative_infinity(self): self.run_case('negative_infinity')
    def test_overflow(self): self.run_case('overflow')
    def test_valid(self): self.run_case('valid')
    def test_zero_is_valid(self): self.run_case('zero')
    def test_provider_error_logs_do_not_expose_content(self): self.run_case('provider_error_log')
