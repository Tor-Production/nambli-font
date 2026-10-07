"""Guard against binary-only, skipped-tofu and unsuccessful package false PASS."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import run_qa

def report(severity='PASS',check='googlefonts/tofu'):
    return {'summary':{severity:1},'results':{'METADATA.pb':{'section':[
        {'check_id':check,'subresults':[{'severity':severity,'code':'fixture','message':'fixture'}]}]}}}

class PackageScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('NAMBLI_QA_TMPDIR'))
        self.root=Path(self.temp.name)
        self.family=self.root/'family'; self.family.mkdir()
        for i in range(12): (self.family/f'Nambli-{i}.ttf').write_bytes(b'fixture')
        self.exe=self.root/'tool.exe'; self.exe.write_bytes(b'fixture')
    def tearDown(self): self.temp.cleanup()
    def package(self):
        (self.family/'METADATA.pb').write_text('\n'.join(f'fonts {{ filename: "Nambli-{i}.ttf" }}' for i in range(12))+'\nsubsets: "latin"')
        (self.family/'OFL.txt').write_text('fixture')
        (self.family/'article').mkdir()
        (self.family/'article/ARTICLE.en_us.html').write_text('<p>fixture</p>')
    def test_ttf_only_cannot_enter_package_scope(self):
        with self.assertRaisesRegex(ValueError,'METADATA'): run_qa.collect_inputs('package',self.family)
        self.assertEqual(len(run_qa.collect_inputs('binary',self.family)),12)
    def test_missing_article_rejected(self):
        self.package(); (self.family/'article/ARTICLE.en_us.html').unlink()
        with self.assertRaisesRegex(ValueError,'ARTICLE'): run_qa.collect_inputs('package',self.family)
    def test_wrong_metadata_font_set_rejected(self):
        self.package(); (self.family/'METADATA.pb').write_text('filename: "other.ttf"\nsubsets: "latin"')
        with self.assertRaisesRegex(ValueError,'enumerate'): run_qa.collect_inputs('package',self.family)
    def test_referenced_article_image_is_an_explicit_input(self):
        self.package()
        article=self.family/'article/ARTICLE.en_us.html'
        article.write_text('<p>fixture</p><img src="specimen.jpg" />')
        with self.assertRaisesRegex(ValueError,'image'): run_qa.collect_inputs('package',self.family)
        image=self.family/'article/specimen.jpg'; image.write_bytes(b'fixture')
        self.assertIn(image.resolve(),run_qa.collect_inputs('package',self.family))
    def test_tofu_skip_or_absence_cannot_pass_package(self):
        for raw in [report('SKIP'),report(check='other')]:
            self.assertFalse(run_qa.assess(raw,'package')['scope_gate_passed'])
    def test_fail_subresult_cannot_pass(self):
        self.assertFalse(run_qa.assess(report('FAIL'),'package')['zero_fail_error_fatal'])
    def execute(self,native_exit=0,mutate=False):
        self.package()
        def fake_run(command,**kw):
            if '--version' in command: return subprocess.CompletedProcess(command,0,b'fixture version',b'')
            Path(command[command.index('--json')+1]).write_text(json.dumps(report()))
            if mutate: (self.family/'OFL.txt').write_text('changed')
            return subprocess.CompletedProcess(command,native_exit,b'fixture',b'')
        with patch('run_qa.subprocess.run',side_effect=fake_run):
            result=run_qa.run('package',self.family,self.exe,self.root/'run')
        return result,json.loads((self.root/'run/summary.json').read_text())
    def test_native_failure_not_hidden_by_green_report(self):
        result,data=self.execute(native_exit=7)
        self.assertEqual(result,1); self.assertEqual(data['native_exit_code'],7); self.assertFalse(data['qa_passed'])
    def test_changed_input_cannot_pass(self):
        result,data=self.execute(mutate=True)
        self.assertEqual(result,1); self.assertFalse(data['all_files_unchanged'])
    def test_complete_success_records_raw_hash_and_scope(self):
        result,data=self.execute()
        self.assertEqual(result,0); self.assertEqual(len(data['explicit_inputs']),15)
        self.assertTrue(data['tofu_executed']); self.assertEqual(len(data['raw_report_sha256']),64)
        with self.assertRaises(FileExistsError): run_qa.run('package',self.family,self.exe,self.root/'run')

if __name__=='__main__': unittest.main()
