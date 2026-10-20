"""Execute the real trial shell script with failing commands; never start Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'recovery/mac-ui-candidate/mac-synthetic-trial.sh'


class TrialSafety(unittest.TestCase):
    def trial(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); home=root/'home';home.mkdir()
            original=root/'original';original.mkdir();(original/'preserve.txt').write_text('unchanged')
            bin_dir=root/'bin';bin_dir.mkdir();log=root/'commands'
            mock=bin_dir/'git'
            mock.write_text('''#!/usr/bin/env bash
set -eu
printf '%s %s\\n' "$PWD" "$*" >> "$COMMAND_LOG"
case "$1" in
 bundle) exit 0;;
 clone)
   if [[ "$FAIL_MODE" = clone ]]; then exit 73; fi
   if [[ "$FAIL_MODE" = cd ]]; then exit 0; fi
   mkdir -p "${@: -1}/.git";exit 0;;
 rev-parse)
   if [[ "$2" = --show-toplevel ]]; then printf '%s\\n' "$PWD";exit 0;fi
   if [[ "$FAIL_MODE" = assertion-command ]]; then exit 74; fi
   if [[ "$FAIL_MODE" = assertion ]]; then printf 'WRONG-COMMIT\\n';exit 0;fi;;
esac
printf 'Unexpected command reached\\n' >&2
exit 91
''');mock.chmod(0o700)
            bundle=root/'candidate.bundle'
            if mode!='missing':bundle.write_text('synthetic bundle stand-in')
            result=subprocess.run(['bash',str(SCRIPT),str(bundle)],cwd=original,
                env={**os.environ,'HOME':str(home),'PATH':str(bin_dir)+os.pathsep+os.environ['PATH'],
                     'COMMAND_LOG':str(log),'FAIL_MODE':mode},capture_output=True,text=True)
            commands=log.read_text() if log.exists() else ''
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertNotIn(' checkout ',commands)
            self.assertEqual((original/'preserve.txt').read_text(),'unchanged')
            self.assertEqual(list(original.iterdir()),[original/'preserve.txt'])
            self.assertIn('Trial stopped with status',result.stderr)
            return result.returncode

    def test_missing_bundle(self):self.trial('missing')
    def test_failed_clone_preserves_73(self):self.assertEqual(self.trial('clone'),73)
    def test_failed_directory_change(self):self.trial('cd')
    def test_failed_commit_assertion(self):self.trial('assertion')
    def test_failed_commit_lookup_preserves_74(self):self.assertEqual(self.trial('assertion-command'),74)

    def test_evidence_verification_failure_is_not_masked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'venv/bin').mkdir(parents=True)
            (root/'venv/bin/python').symlink_to(sys.executable)
            evidence=root/'evidence';evidence.mkdir()
            (evidence/'stack-results.json').write_text(json.dumps({
                'original_local_containers_unchanged':False,
                'original_local_volume_names_unchanged':True,'tests':{'restart':{}}}))
            source=SCRIPT.read_text()
            block=source[source.index('"$TRIAL_ROOT/venv/bin/python" - <<'):]
            result=subprocess.run(['bash','-Eeuo','pipefail','-c',block],cwd=root,
                env={**os.environ,'TRIAL_ROOT':str(root),'DOCLENS_CANDIDATE_EVIDENCE':str(evidence)},
                capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('AssertionError',result.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
