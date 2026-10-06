import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from saveconfig.smb import share_uri,local_share,ensure_available
from saveconfig.settings import Settings

ROOT=Path(__file__).resolve().parents[1]

class SmbTests(unittest.TestCase):
    def test_uri_validation(self):
        self.assertEqual(share_uri('OMV.local','Sicherung Josef'),'smb://omv.local/Sicherung%20Josef')
        for server,share in [('','backup'),('smb://omv','backup'),('omv','../backup'),('omv',''),('omv','a\\b')]:
            with self.assertRaises(ValueError):share_uri(server,share)
    def test_only_matching_mounted_share(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            root=Path(folder);target=root/'smb-share:server=omv.local,share=backup';target.mkdir()
            self.assertEqual(local_share('smb://omv.local/backup',root),target)
            with self.assertRaises(ValueError):local_share('smb://other/backup',root)
    def test_disconnected_target_rejected_before_creation(self):
        target=Path('/run/user')/str(os.getuid())/'gvfs/smb-share:server=not-connected,share=backup'
        with patch('saveconfig.smb.os.path.ismount',return_value=False):
            with self.assertRaisesRegex(ValueError,'smb_unavailable'):ensure_available(target)
        self.assertFalse(target.exists())
    def test_settings_roundtrip_without_password(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            s=Settings(Path(folder));s.data.update(smb_server='omv.local',smb_share='backup');s.save()
            loaded=Settings(Path(folder))
            self.assertEqual(loaded.data['smb_server'],'omv.local')
            self.assertEqual(loaded.data['smb_share'],'backup')
            self.assertFalse(any('password' in key for key in loaded.data))

    def test_ssh_alias_used_without_connecting(self):
        import subprocess
        with patch('saveconfig.smb.subprocess.run',return_value=subprocess.CompletedProcess([],0,'hostname 10.0.0.120\nuser josef\n','')) as run:
            self.assertEqual(share_uri('omv','backup'),'smb://10.0.0.120/backup')
            self.assertIn('-G',run.call_args.args[0])
    def test_missing_alias_reported(self):
        import subprocess
        with patch('saveconfig.smb.subprocess.run',return_value=subprocess.CompletedProcess([],0,'hostname omv\n','')):
            with self.assertRaisesRegex(ValueError,'smb_alias_missing'):share_uri('omv','backup')

    def test_declared_network_mount_rejects_missing_and_wrong_source(self):
        from saveconfig.smb import ensure_network_mount
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            mount=Path(folder)/'mount';destination=mount/'backup'
            line=f'42 1 0:1 / {mount} rw - cifs //omv/backup rw\n'
            with patch('saveconfig.smb.Path.read_text',return_value=line),patch('saveconfig.smb.os.path.ismount',return_value=True):
                ensure_network_mount(destination,str(mount),'//omv/backup')
                with self.assertRaisesRegex(ValueError,'network_mount_required'):ensure_network_mount(destination,str(mount),'//other/backup')
            with patch('saveconfig.smb.Path.read_text',return_value=''):
                with self.assertRaisesRegex(ValueError,'network_mount_required'):ensure_network_mount(destination,str(mount),'//omv/backup')
            self.assertFalse(mount.exists())

    def test_network_backup_never_creates_fallback_directory(self):
        from saveconfig.backup import backup
        from saveconfig.models import Operation
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            mount=Path(folder)/'mount';destination=mount/'backup'
            with patch('saveconfig.smb.Path.read_text',return_value=''):
                with self.assertRaisesRegex(ValueError,'network_mount_required'):
                    backup(None,folder,destination,[],Operation(),target_kind='network',mount_point=str(mount),mount_source='//omv/backup')
            self.assertFalse(mount.exists())
