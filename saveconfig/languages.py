import json
import re
import string
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
from .utils import atomic_json, read_json_limited
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent


class OfflineHelp(HTMLParser):
    tags={'html','head','body','main','meta','title','section','h1','h2','h3','h4','p','ul','ol','li','dl','dt','dd','table','thead','tbody','tr','th','td','br','hr','pre','code','span','div','strong','em','a','img'}
    attributes={'lang','dir','charset','name','content','id','class','title','alt','width','height','href','src'}
    def handle_starttag(self,tag,attrs):
        if tag not in self.tags:raise ValueError('invalid_language')
        for key,value in attrs:
            if key not in self.attributes or value is None:raise ValueError('invalid_language')
            if key in ('src','href'):
                logo=re.search(r'<img\b[^>]*\bsrc="([^"]+)"', (ROOT/'help/en/index.html').read_text('utf-8'))
                valid=(key=='href' and value.startswith('#')) or (tag=='img' and key=='src' and logo and value==logo.group(1) and value.startswith('data:image/png;base64,'))
                if not valid:raise ValueError('invalid_language')
        if tag=='meta' and any(key not in ('charset','name','content') for key,_ in attrs):raise ValueError('invalid_language')
    handle_startendtag=handle_starttag


def github_json(url,maximum=2_000_000):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in ('raw.githubusercontent.com','github.com','api.github.com') or parts.username or parts.password or 'xxxx' in parts.path.split('/'):
        raise ValueError('https_required')
    with urlopen(url,timeout=15) as response:
        final=urlsplit(response.geturl())
        if final.scheme!='https' or final.hostname not in ('raw.githubusercontent.com','github.com','api.github.com'):
            raise ValueError('https_required')
        data=response.read(maximum+1)
    if len(data)>maximum:raise ValueError('invalid_language')
    return json.loads(data)


def download_version(url):
    return validate_version(github_json(url))


def validate_version(data):
    if not isinstance(data,dict) or data.get('program_id')!='saveconfig' or not isinstance(data.get('version'),str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',data['version']):
        raise ValueError('invalid_version')
    return data['version']

class Languages:
    def __init__(self, settings):
        self.settings = settings
        self.folder = settings.root / '.local/share/saveconfig/languages'
        self.packs = {}
        self.reload()

    def reload(self):
        self.packs={}
        for folder in (ROOT / 'lang', self.folder):
            if folder.exists():
                for path in folder.glob('*.json'):
                    try:
                        pack = json.loads(path.read_text(encoding='utf-8'))
                        self.validate(pack, baseline=False, trusted=folder==ROOT/'lang')
                        self.packs[pack['code']] = pack
                    except (ValueError, OSError, KeyError):
                        continue

    def validate(self, pack, baseline=True, trusted=False):
        if not isinstance(pack, dict) or pack.get('program_id') != 'saveconfig' or not isinstance(pack.get('code'),str) or not re.fullmatch('[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', pack['code']):
            raise ValueError('invalid_language')
        if not isinstance(pack.get('name'), str) or not isinstance(pack.get('help_html'), str) or not isinstance(pack.get('strings'), dict):
            raise ValueError('invalid_language')
        if not all(isinstance(v, str) for v in pack['strings'].values()):
            raise ValueError('invalid_language')
        if baseline:
            reference = self.packs['en']['strings']
            if reference.keys() != pack['strings'].keys():
                raise ValueError('invalid_language')
            parser = string.Formatter()
            for key, value in reference.items():
                fields = lambda text: {field for _, field, _, _ in parser.parse(text) if field}
                if fields(value) != fields(pack['strings'][key]):
                    raise ValueError('invalid_language')
        if len(json.dumps(pack,ensure_ascii=False).encode('utf-8'))>2_000_000:raise ValueError('invalid_language')
        if not trusted:
            parser=OfflineHelp(convert_charrefs=True);parser.feed(pack['help_html']);parser.close()
        # HTML is displayed as an offline document, never inside a privileged view.
        if re.search(r'<\s*(script|iframe|object|embed|form)\b|\bon\w+\s*=|javascript:', pack['help_html'], re.I):
            raise ValueError('invalid_language')

    def install_file(self, path):
        return self.install(read_json_limited(path,2_000_000,'invalid_language'))

    def install(self, pack):
        self.validate(pack)
        if pack['code'] in self.packs:
            raise ValueError('language_exists')
        atomic_json(self.folder / (pack['code'] + '.json'), pack)
        self.reload()

    def text(self, key):
        code = self.settings.data['language']
        return self.packs.get(code, self.packs['en'])['strings'].get(key, self.packs['en']['strings'].get(key, key))

    def language_name(self,code,fallback=None):
        value=self.text('language_name_'+code)
        if value!='language_name_'+code:return value
        return fallback or self.packs.get(code,{}).get('name') or code

    def catalog(self, base):
        data=github_json(base.rstrip('/')+'/catalog.json',1_000_000)
        if not isinstance(data, dict) or data.get('program_id') != 'saveconfig' or not isinstance(data.get('languages'), list):
            raise ValueError('invalid_language')
        for item in data['languages']:
            if not isinstance(item,dict) or not isinstance(item.get('code'),str) or not re.fullmatch('[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', item['code']) or not isinstance(item.get('name'), str):
                raise ValueError('invalid_language')
        return [p for p in data['languages'] if p['code'] not in self.packs]

    def download(self, base, code):
        if not isinstance(code,str) or not re.fullmatch('[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*',code):raise ValueError('invalid_language')
        pack=github_json(base.rstrip('/')+'/'+code+'.json')
        if not isinstance(pack,dict) or pack.get('code') != code:
            raise ValueError('invalid_language')
        self.install(pack)
        return code
