"""Expected failing fixture controls; exit 0 only if both corruptions are caught.

Mutates disposable synthetic copies only, never repository originals or user data.
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import test_stage1_contract as contract


def main():
    original=contract.FIXTURES
    cases=[('corrupt-original','test_original_bytes_hashes_sizes_and_pdf_offsets'),
           ('retarget-historical-citation','test_graph_references_and_exact_excerpt_identity')]
    try:
        for name,method in cases:
            with tempfile.TemporaryDirectory(prefix='doclens-contract-negative-') as tmp:
                root=Path(tmp)/'fixtures';shutil.copytree(original,root)
                if name=='corrupt-original':
                    path=root/'synthetic-old.pdf';path.write_bytes(path.read_bytes()+b'Synthetic corruption')
                else:
                    path=root/'preservation.json';fixture=json.loads(path.read_text())
                    fixture['citations'][0]['version_id']=fixture['platform']['documents'][0]['active_version_id']
                    path.write_text(json.dumps(fixture))
                contract.FIXTURES=root
                print('EXPECTED NEGATIVE CONTROL:',name,flush=True)
                result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([contract.PreservationExamples(method)]))
                if result.testsRun!=1 or len(result.failures)!=1 or result.errors:
                    raise AssertionError('Negative control did not fail in the expected assertion')
                print('PASS: intentionally damaged synthetic copy rejected; repository fixture untouched',flush=True)
    finally:contract.FIXTURES=original
    return 0


if __name__=='__main__':raise SystemExit(main())
