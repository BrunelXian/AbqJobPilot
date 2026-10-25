"""Design artifact checks only. Does not import AbqJobPilot or contact a service."""
import csv
import json
from pathlib import Path
import re
import unittest

HERE=Path(__file__).resolve().parent
DESIGN=HERE/'design'
HTML=(DESIGN/'index.html').read_text(encoding='utf-8')
LOCALES={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (DESIGN/'locales').glob('*.json')}

class DesignChecks(unittest.TestCase):
    def test_exact_four_locales(self):
        self.assertEqual(set(LOCALES),{'en','zh-CN','fr-FR','de-DE'})
    def test_keys_and_nonempty_values(self):
        for locale,values in LOCALES.items():
            self.assertEqual(set(values),set(LOCALES['en']),locale)
            self.assertTrue(all(isinstance(v,str) and v.strip() for v in values.values()),locale)
    def test_no_duplicate_source_keys(self):
        with (DESIGN/'strings.tsv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f,delimiter='\t'))
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        self.assertTrue(all(set(r)=={'key','en','zh-CN','fr-FR','de-DE'} for r in rows))
    def test_placeholder_parity(self):
        for locale,values in LOCALES.items():
            for key,text in values.items():
                self.assertEqual(re.findall(r'\{\w+\}',text),re.findall(r'\{\w+\}',LOCALES['en'][key]),(locale,key))
    def test_all_literal_translation_keys_present(self):
        for key in re.findall(r"\bt\('([^']+)'",HTML):self.assertIn(key,LOCALES['en'])
    def test_inlined_catalog(self):
        self.assertNotIn('/* RESOURCE_CATALOG */',HTML)
        self.assertIn('const catalog = ',HTML)
    def test_no_external_resource_or_request(self):
        self.assertNotRegex(HTML,r'<(?:script|link|img)[^>]+(?:src|href)=')
        self.assertNotRegex(HTML,r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(')
        self.assertIn("connect-src 'none'",HTML)
        self.assertIn("form-action 'none'",HTML)
    def test_default_english_and_design_label(self):
        self.assertIn("params.get('lang'):'en'",HTML)
        self.assertIn('Synthetic data · no service connection · no execution',HTML)
    def test_navigation_and_no_real_launch_surface(self):
        self.assertIn("'overview','projects','queue','runs','results','agent','classic','settings','service'",HTML)
        self.assertNotIn('abq2024.bat',HTML)
        self.assertNotIn('approved=true',HTML)
        self.assertNotIn('D:\\ABAQUS',HTML)
    def test_local_document_links_exist(self):
        for p in HERE.glob('*.md'):
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):continue
                self.assertTrue((p.parent/target.split('#')[0]).exists(),(p.name,target))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DesignChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'scope':'Design artifacts, not application regression','tests':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'resource_keys_per_locale':len(LOCALES['en'])}
    (HERE/'DESIGN_CHECKS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
