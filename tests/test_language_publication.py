import json,tempfile,unittest
from pathlib import Path
from saveconfig.languages import Languages
from saveconfig import VERSION
from saveconfig.settings import Settings
ROOT=Path(__file__).resolve().parents[1]
class LanguagePublicationTests(unittest.TestCase):
 def test_current_packs_and_safe_offline_logo(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
   languages=Languages(Settings(Path(folder)))
   packs=list((ROOT/'github/sprachpakete').glob('*.json'))
   self.assertEqual(len(packs),9)
   for path in packs:
    if path.stem=='catalog':continue
    pack=json.loads(path.read_text());languages.validate(pack)
    self.assertEqual(pack['application_version'],VERSION)
    self.assertIn('data:image/png;base64,',pack['help_html'])
    self.assertIn('F1',pack['help_html'])
   pack=json.loads((ROOT/'github/sprachpakete/fr.json').read_text())
   pack['help_html']=pack['help_html'].replace('</h1>','</h1><img src="https://example.invalid/tracker.png">')
   with self.assertRaises(ValueError):languages.validate(pack)
