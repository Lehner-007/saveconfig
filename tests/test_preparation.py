import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('package_tools', ROOT / 'tools/package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.root = Path(self.temp.name)
        for name in ['saveconfig.py', 'README.md', 'LICENSE']:
            (self.root / name).write_text('neutral')
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test.py').write_text('test source')
        (self.root / 'tests/__pycache__').mkdir()
        (self.root / 'tests/__pycache__/cache.pyc').write_bytes(b'cache')

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, version='0.1.0'):
        with patch.object(package, 'ROOT', self.root), patch.object(package, 'VERSION', version), patch.object(package, 'SOURCE', ['saveconfig.py', 'README.md', 'LICENSE', 'tests']), patch('sys.argv', ['package.py', 'source']), contextlib.redirect_stdout(io.StringIO()):
            package.main()

    def test_source_scope_and_preservation(self):
        before = (self.root / 'saveconfig.py').read_bytes()
        self.invoke()
        self.invoke()
        folders = list((self.root / 'dist').iterdir())
        self.assertEqual(len(folders), 2)
        for folder in folders:
            self.assertTrue((folder / 'tests/test.py').is_file())
            self.assertFalse((folder / 'tests/__pycache__').exists())
        self.assertEqual(before, (self.root / 'saveconfig.py').read_bytes())

    def test_invalid_versions(self):
        for version in ['', '1.0', 'invalid']:
            with self.assertRaises(ValueError):
                self.invoke(version)

    def test_missing_license(self):
        (self.root / 'LICENSE').unlink()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_env_blocks(self):
        (self.root / '.env').write_text('neutral')
        with self.assertRaises(ValueError):
            self.invoke()

    def test_symlink_blocks(self):
        (self.root / 'tests/outside').symlink_to(self.root / 'README.md')
        with self.assertRaises(ValueError):
            self.invoke()

    def test_obvious_secret_blocks_without_value(self):
        secret = 'gh' + 'p_' + ('A' * 30)
        path = self.root / 'saveconfig.py'
        path.write_text(secret)
        with self.assertRaises(ValueError) as result:
            self.invoke()
        self.assertNotIn(secret, str(result.exception))
        self.assertEqual(path.read_text(), secret)
