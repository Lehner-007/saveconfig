import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import test_core
from saveconfig.settings import Settings
from saveconfig.backup import backup
from saveconfig.verify import contained, load_manifest, verify
from saveconfig.restore import preview
from saveconfig.languages import Languages

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_core.CoreTests(); self.fixture.setUp()
    def tearDown(self): self.fixture.tearDown()
    def test_dot_path_rejected(self):
        for value in ('.', '..', 'home/../outside', '/outside', ''):
            with self.assertRaises(ValueError): contained(self.fixture.root,value)
    def test_null_record_rejected(self):
        f,m=self.fixture.snapshot(); m['files']=[None]
        (f/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError): load_manifest(f)
    def test_corrupt_daily_reuse_rejected(self):
        t=self.fixture; f,m=t.snapshot()
        (f/'home/.config/filezilla/sitemanager.xml').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'daily_backup_invalid'):
            backup(t.db,t.home,t.target,t.entries(),t.op)
    def test_extra_file_and_readonly_preview(self):
        t=self.fixture; f,m=t.snapshot(); (f/'unexpected').write_text('extra')
        self.assertIn('extra:unexpected',verify(f,t.op,write_result=False))
        self.assertFalse((f/'verification.json').exists())
        rows=preview(f,t.home,t.op)
        self.assertTrue(rows); self.assertEqual(rows[0]['integrity'],'verification_failed')
        self.assertFalse((f/'verification.json').exists())
    def test_xattrs_saved_and_checked(self):
        t=self.fixture; src=t.home/'.config/filezilla/sitemanager.xml'
        os.setxattr(src,'user.saveconfig-test',b'attribute')
        f,m=t.snapshot(); target=f/'home/.config/filezilla/sitemanager.xml'
        self.assertEqual(os.getxattr(target,'user.saveconfig-test'),b'attribute')
        self.assertEqual(verify(f,t.op),[])
        os.setxattr(target,'user.saveconfig-test',b'changed')
        self.assertIn('home/.config/filezilla/sitemanager.xml',verify(f,t.op))
    def test_remote_help_rejected(self):
        lang=Languages(Settings(self.fixture.root/'languages')); pack=dict(lang.packs['en'])
        for html in ('<img src="https://example.org/a">','<style>@import "https://example.org/a";</style>','<p style="background:url(https://example.org/a)">text</p>'):
            pack['help_html']=html
            with self.assertRaises(ValueError): lang.validate(pack)

    def test_corrupt_catalog_preserved(self):
        import subprocess
        from saveconfig.settings import Settings
        root=self.fixture.root/'broken-state'; settings=Settings(root)
        settings.db_path.parent.mkdir(parents=True,exist_ok=True)
        settings.db_path.write_bytes(b'broken database')
        result=subprocess.run(['/usr/bin/python3','-B',str(Path(__file__).resolve().parents[1]/'saveconfig.py'),'--state-home',str(root),'scan'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout)['code'],'catalog_unavailable')
        self.assertNotIn('Traceback',result.stderr)
        self.assertEqual(settings.db_path.read_bytes(),b'broken database')
    def test_cleanup_preserves_personal_and_backups(self):
        import tools_cleanup as cleanup
        home=self.fixture.root/'cleanup-home'; app=home/'.local/share/applications'; app.mkdir(parents=True)
        (app/'managed.desktop').write_text(cleanup.MANAGED.replace('Exec=saveconfig','Exec=env LANG=de /usr/bin/saveconfig'))
        personal=app/'personal.desktop'; personal.write_text('[Desktop Entry]\nType=Application\nName=Personal\nExec=saveconfig --home /other\n')
        runtime=home/'.config/saveconfig'; runtime.mkdir(parents=True); (runtime/'settings.json').write_text('{}')
        external=home/'backups'; external.mkdir(); (external/'original').write_text('keep')
        with patch.dict(os.environ,{name:'' for name in ('XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','XDG_STATE_HOME')}):
            cleanup.user_action('upgrade',home)
            self.assertTrue(runtime.exists())
            self.assertTrue(cleanup.user_action('remove',home))
            self.assertTrue(cleanup.user_action('purge',home))
        self.assertFalse(runtime.exists()); self.assertFalse((app/'managed.desktop').exists())
        self.assertTrue(personal.exists()); self.assertEqual((external/'original').read_text(),'keep')

    def test_manifest_size_limit_and_separate_error(self):
        import saveconfig.verify as module
        self.assertGreaterEqual(module.MAX_MANIFEST_BYTES, 73835537)
        folder,_=self.fixture.snapshot()
        with patch.object(module,'MAX_MANIFEST_BYTES',10):
            with self.assertRaisesRegex(ValueError,'manifest_too_large'):module.load_manifest(folder)

    def test_manifest_cancel_during_validation(self):
        from saveconfig.models import Operation, Cancelled
        folder,_=self.fixture.snapshot()
        op=Operation(); counter=[0]
        original=op.check
        def check():
            counter[0]+=1
            if counter[0]==8:op.cancel.set()
            original()
        op.check=check
        with self.assertRaises(Cancelled):load_manifest(folder,op)
        self.assertFalse((folder/'verification.json').exists())

    def test_directory_attributes_checked(self):
        t=self.fixture;src=t.home/'.config/filezilla'
        os.setxattr(src,'user.qa',b'attribute')
        folder,_=t.snapshot();target=folder/'home/.config/filezilla'
        self.assertEqual(os.getxattr(target,'user.qa'),b'attribute')
        self.assertEqual(verify(folder,t.op,write_result=False),[])
        os.removexattr(target,'user.qa')
        self.assertIn('home/.config/filezilla',verify(folder,t.op,write_result=False))
    def test_protected_cleanup_is_incomplete(self):
        import tools_cleanup as cleanup
        root=self.fixture.root;home=root/'protected-home';home.mkdir()
        external=root/'protected-external';(external/'saveconfig').mkdir(parents=True)
        original=external/'saveconfig/settings.json';original.write_text('keep')
        (home/'.config').symlink_to(external,target_is_directory=True)
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(cleanup.user_action('purge',home))
        self.assertEqual(original.read_text(),'keep')

    def test_cache_excluded_even_inside_selected_program(self):
        t=self.fixture;folder=t.home/'.config/filezilla/Cache';folder.mkdir();(folder/'temporary').write_text('cache')
        from saveconfig.models import Entry
        entries=t.entries();cache=t.home/'.cache/test';cache.mkdir(parents=True);(cache/'x').write_text('cache')
        entries.append(Entry('Cache','~/.cache/test',selected=True,exists=True))
        with patch('saveconfig.backup.inventory',return_value={'installed':[],'manual':[],'automatic':[]}):
            saved,m=backup(t.db,t.home,t.target,entries,t.op)
        self.assertFalse((saved/'home/.cache').exists())
        self.assertFalse((saved/'home/.config/filezilla/Cache').exists())
        self.assertEqual(verify(saved,t.op),[])

    def test_codex_excluded_from_scan_and_forced_backup(self):
        from saveconfig.scanner import scan
        from saveconfig.models import Entry
        t=self.fixture;folder=t.home/'.codex';folder.mkdir();(folder/'state').write_text('private')
        entries,_=scan(t.db,t.home,t.op)
        self.assertNotIn('~/.codex',[e.path for e in entries])
        entries=t.entries()+[Entry('Codex','~/.codex',selected=True,exists=True)]
        nested=t.home/'.config/filezilla/Codex';nested.mkdir();(nested/'private').write_text('private')
        with patch('saveconfig.backup.inventory',return_value={'installed':[],'manual':[],'automatic':[]}):
            saved,m=backup(t.db,t.home,t.target,entries,t.op)
        self.assertFalse((saved/'home/.codex').exists())
        self.assertFalse((saved/'home/.config/filezilla/Codex').exists())
        self.assertEqual(verify(saved,t.op),[])
