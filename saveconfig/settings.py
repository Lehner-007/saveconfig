import json
import os
import shutil
import uuid
from pathlib import Path
from .utils import atomic_json
from .classification import FILTER_DEFAULTS
from .model import PROJECT

class Settings:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path.home()
        self.file = self.root / '.config/saveconfig/settings.json'
        self.data = dict(target_kind='local', mount_point='', mount_source='', smb_server='omv', smb_share='', config_version=2, home=str(Path.home()), destination='', language='de', geometry='1180x720', github_source='', active_profile='', display_filters=dict(FILTER_DEFAULTS),
                         window_x=0,window_y=0,window_position_known=False,window_maximized=False,
                         update_url='',update_check=False,update_interval_value=1,update_interval_unit='weeks',last_update_check='')
        self.warning = False
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('settings')
                for key in self.data:
                    if key in data and type(data[key]) is type(self.data[key]):
                        self.data[key] = data[key]
                self.data['display_filters'] = {key: self.data['display_filters'].get(key, default) if type(self.data['display_filters'].get(key)) is bool else default for key, default in FILTER_DEFAULTS.items()}
            except (OSError, ValueError):
                self.warning = True
        if self.data['target_kind'] not in ('local','network'):self.data['target_kind']='local'
        self.data['github_source']=PROJECT['source_url']
        self.data['update_url']=PROJECT['update_url']
        self.data['config_version']=2
        self.data['update_interval_value']=max(1,min(365,self.data['update_interval_value']))
        if self.data['update_interval_unit'] not in ('days','weeks','months'):self.data['update_interval_unit']='weeks'
        try:
            width,height=map(int,self.data['geometry'].split('x'))
            if width<=0 or height<=0:raise ValueError('geometry')
        except ValueError:self.data['geometry']='1180x720'

    @property
    def db_path(self):
        return self.root / '.local/share/saveconfig/saveconfig.db'

    def remember_installed_locations(self):
        from .languages import ROOT
        import os
        if ROOT!=Path('/usr/share/saveconfig') or os.geteuid()==0:return
        registry=Path.home()/'.local/state/saveconfig-locations.json'
        if any(p.is_symlink() for p in (registry,*registry.parents)):raise ValueError('unsafe_registry')
        locations=set()
        if registry.exists():
            data=json.loads(registry.read_text())
            if not isinstance(data,dict) or data.get('program_id')!='saveconfig' or not isinstance(data.get('locations'),list):raise ValueError('unsafe_registry')
            locations.update(v for v in data['locations'] if isinstance(v,str) and Path(v).is_absolute() and Path(v).name=='saveconfig')
        locations.update(str(self.root/part/'saveconfig') for part in ('.config','.local/share','.local/state','.cache'))
        atomic_json(registry,dict(program_id='saveconfig',locations=sorted(locations)))

    def save(self):
        if self.warning and self.file.exists():
            shutil.copy2(self.file, self.file.with_name('settings.invalid-' + uuid.uuid4().hex + '.json'))
            self.warning = False
        atomic_json(self.file, self.data)
