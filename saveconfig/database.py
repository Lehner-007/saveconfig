import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .utils import now
from .classification import category_for, CATEGORIES

KNOWN = [
    ('FileZilla', 'filezilla', '~/.config/filezilla', 'config', True),
    ('Firefox', 'firefox', '~/.mozilla', 'profile', True),
    ('VSCodium', 'codium', '~/.config/VSCodium', 'config', False),
    ('Nemo', 'nemo', '~/.config/nemo', 'config', False),
    ('Restic', 'restic', '~/.config/restic', 'config', True),
    ('SSH', 'openssh-client', '~/.ssh', 'key', True),
    ('GnuPG', 'gnupg', '~/.gnupg', 'key', True),
    ('Cinnamon', 'cinnamon', '~/.config/cinnamon', 'config', False),
    ('Cinnamon', 'cinnamon', '~/.config/cinnamon-monitors.xml', 'config', False),
    ('Cinnamon', 'cinnamon', '~/.config/dconf', 'config', False),
    ('System', '', '/etc/fstab', 'system', True),
    ('System', '', '/etc/hosts', 'system', False),
]

class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS programs(id INTEGER PRIMARY KEY, name TEXT UNIQUE, package_name TEXT, package_type TEXT, description TEXT, enabled INTEGER, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS config_paths(id INTEGER PRIMARY KEY, program_id INTEGER REFERENCES programs(id), path TEXT UNIQUE, path_type TEXT, required INTEGER, sensitive INTEGER, enabled INTEGER, notes TEXT);
            CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, scan_date TEXT, home_path TEXT, hostname TEXT, status TEXT, duration REAL, notes TEXT);
            CREATE TABLE IF NOT EXISTS scan_results(id INTEGER PRIMARY KEY, scan_id INTEGER REFERENCES scans(id), config_path_id INTEGER, actual_path TEXT, "exists" INTEGER, size INTEGER, file_count INTEGER, modified REAL, status TEXT);
            CREATE TABLE IF NOT EXISTS backups(id INTEGER PRIMARY KEY, backup_date TEXT, destination TEXT, backup_directory TEXT, status TEXT, file_count INTEGER, total_size INTEGER, verified INTEGER, notes TEXT);
            ''')
        with self.connect() as db:
            for table in ('config_paths', 'scan_results'):
                columns = {row['name'] for row in db.execute('PRAGMA table_info(' + table + ')')}
                if 'category' not in columns:
                    db.execute("ALTER TABLE " + table + " ADD COLUMN category TEXT NOT NULL DEFAULT 'unknown'")
            db.execute('PRAGMA user_version=1')
        with self.connect() as db:
            for row in db.execute('SELECT c.id,c.path,c.path_type,p.name FROM config_paths c JOIN programs p ON p.id=c.program_id WHERE c.category=?', ('unknown',)).fetchall():
                db.execute('UPDATE config_paths SET category=? WHERE id=?', (category_for(row['path'], row['path_type'], True, row['name']), row['id']))
        self.path.chmod(0o600)
        for name, package, path, kind, sensitive in KNOWN:
            self.learn(name, package, path, kind, sensitive, kind != 'system' and name != 'Cinnamon', '', seed=True)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def learn(self, name, package, path, kind, sensitive, enabled, notes, seed=False, category=None):
        category = category or category_for(path, kind, True, name)
        if category not in CATEGORIES:
            raise ValueError('invalid_category')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO programs VALUES(NULL,?,?,?,?,?,?,?)', (name, package, 'system' if kind == 'system' else 'unknown', '', 1, now(), now()))
            program = db.execute('SELECT id FROM programs WHERE name=?', (name,)).fetchone()[0]
            if seed:
                db.execute('INSERT OR IGNORE INTO config_paths(program_id,path,path_type,required,sensitive,enabled,notes,category) VALUES(?,?,?,?,?,?,?,?)', (program, path, kind, 0, sensitive, enabled, notes, category))
            else:
                db.execute('INSERT INTO config_paths(program_id,path,path_type,required,sensitive,enabled,notes,category) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET program_id=excluded.program_id,path_type=excluded.path_type,sensitive=excluded.sensitive,enabled=excluded.enabled,notes=excluded.notes,category=excluded.category', (program, path, kind, 0, sensitive, enabled, notes, category))

    def classify(self, path, category, kind):
        if category not in CATEGORIES:
            raise ValueError('invalid_category')
        with self.connect() as db:
            row = db.execute('SELECT id FROM config_paths WHERE path=?', (path,)).fetchone()
            if row:
                db.execute('UPDATE config_paths SET category=?,path_type=? WHERE id=?', (category, kind, row['id']))
                return
        self.learn('Cinnamon' if category == 'system_desktop' and path in ('~/.config/cinnamon', '~/.config/cinnamon-monitors.xml') else 'Katalog', '', path, kind, True, False, '', category=category)

    def catalog(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT c.*,p.name FROM config_paths c JOIN programs p ON p.id=c.program_id WHERE p.enabled=1 ORDER BY p.name,c.path')]

    def snapshot(self, destination):
        with self.connect() as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
