"""Named source profiles, separate from global application preferences."""
import json
import uuid
from pathlib import Path
from .utils import atomic_json, read_json_limited

class Profiles:
    def __init__(self, settings):
        self.folder = settings.file.parent / 'profiles'

    def validate(self, data):
        if not isinstance(data, dict) or data.get('format_version') != 1:
            raise ValueError('invalid_profile')
        for key in ('name', 'home', 'destination'):
            if not isinstance(data.get(key), str):
                raise ValueError('invalid_profile')
        if not data['name'].strip() or len(data['name']) > 120 or not Path(data['home']).is_absolute():
            raise ValueError('invalid_profile')
        if data['destination'] and not Path(data['destination']).is_absolute():
            raise ValueError('invalid_profile')
        if not isinstance(data.get('selection'), list) or not all(isinstance(p, str) for p in data['selection']):
            raise ValueError('invalid_profile')
        if not isinstance(data.get('selection_saved'), bool):
            raise ValueError('invalid_profile')
        for key in ('smb_server','smb_share'):
            value=data.get(key,'')
            if not isinstance(value,str) or len(value)>255 or '\x00' in value:raise ValueError('invalid_profile')
        if any(c in data.get('smb_share','') for c in '/\\'):raise ValueError('invalid_profile')
        data.setdefault('target_kind','local')
        data.setdefault('mount_point','')
        data.setdefault('mount_source','')
        if data['target_kind'] not in ('local','network'):raise ValueError('invalid_profile')
        for key in ('mount_point','mount_source'):
            if not isinstance(data[key],str) or '\x00' in data[key] or len(data[key])>4096:raise ValueError('invalid_profile')
        if data['target_kind']=='network':
            if '..' in Path(data['destination']).parts or '..' in Path(data['mount_point']).parts or not data['mount_point'] or not Path(data['mount_point']).is_absolute() or not data['mount_source'] or not Path(data['destination']).is_relative_to(Path(data['mount_point'])):raise ValueError('invalid_profile')
        return data

    def list(self):
        result = []
        if self.folder.is_dir():
            for path in self.folder.glob('*.json'):
                if path.is_symlink():
                    continue
                try:
                    data = self.validate(json.loads(path.read_text(encoding='utf-8')))
                    result.append((path.stem, data))
                except (OSError, ValueError):
                    continue
        return sorted(result, key=lambda item: item[1]['name'].casefold())

    def get(self, ident):
        if not isinstance(ident, str) or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('invalid_profile')
        path = self.folder / (ident + '.json')
        if path.is_symlink():
            raise ValueError('invalid_profile')
        return self.validate(json.loads(path.read_text(encoding='utf-8')))

    def save(self, data, ident=None):
        self.validate(data)
        existing = self.list()
        if any(p['name'].casefold() == data['name'].casefold() and key != ident for key, p in existing):
            raise ValueError('profile_name_exists')
        if ident is not None:
            self.get(ident)
        else:
            ident = uuid.uuid4().hex
        atomic_json(self.folder / (ident + '.json'), data)
        return ident

    def export(self, ident, target):
        if Path(target).exists() or Path(target).is_symlink():
            raise ValueError('profile_file_exists')
        atomic_json(target, self.get(ident))

    def import_file(self, source):
        return self.save(self.validate(read_json_limited(source,2_000_000,'invalid_profile')))
