import json
import os
import sqlite3
import uuid
import warnings
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def data_directory():
    if os.environ.get('VCR_DATA_DIR'):
        return Path(os.environ['VCR_DATA_DIR']).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ['LOCALAPPDATA']) / 'VoiceControlRoom'
    return Path.home() / '.local' / 'share' / 'voice-control-room'


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback transactions and release Windows file handles on exit."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Store:
    COLUMNS = {
        'profiles': {'id', 'name', 'kind', 'authorization', 'created', 'primary_asset'},
        'assets': {'id', 'profile_id', 'name', 'kind', 'created', 'metadata'},
        'settings': {'key', 'value'},
        'reviews': {'id', 'asset_id', 'data', 'created'},
    }

    @classmethod
    def compatible(cls, path):
        if not path.exists():
            return True
        # Inspect without changing an unfamiliar database, including its journal.
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as c:
            for table, required in cls.COLUMNS.items():
                columns = c.execute(f'PRAGMA table_info({table})').fetchall()
                if not columns:
                    continue
                names = {column[1] for column in columns}
                if not required <= names:
                    return False
                key = 'key' if table == 'settings' else 'id'
                if [column[1] for column in columns if column[5]] != [key]:
                    return False
                if any(column[1] not in required and column[3] and column[4] is None
                       for column in columns):
                    return False
        return True

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.audio = self.root / 'audio'
        self.audio.mkdir(exist_ok=True, mode=0o700)
        self.db = self.root / 'studio.sqlite3'
        self.preserved_database = None
        dedicated = self.root / 'studio-v1.sqlite3'
        if dedicated.exists() or not self.compatible(self.db):
            self.preserved_database = self.db if self.db.exists() else None
            self.db = dedicated
            if not self.compatible(self.db):
                raise RuntimeError('The dedicated studio database has an incompatible layout. Both databases were preserved; restore a verified backup or inspect their schemas before repair.')
            warnings.warn('An earlier database is preserved separately. This studio uses studio-v1.sqlite3; recordings from the earlier app require explicit import.', RuntimeWarning)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                authorization TEXT NOT NULL, created TEXT NOT NULL,
                primary_asset TEXT);
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, name TEXT NOT NULL,
                kind TEXT NOT NULL, created TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS voice_preferences (profile_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recycle_bin (id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS profile_details (
                profile_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')
            c.execute('INSERT OR IGNORE INTO profiles (id,name,kind,authorization,created,primary_asset) VALUES (?,?,?,?,?,NULL)',
                      ('my-voice', 'My Voice', 'self', 'Own voice', now()))
        if os.name != 'nt':
            self.root.chmod(0o700)
            self.db.chmod(0o600)

    def connect(self):
        c = sqlite3.connect(self.db, timeout=30, factory=ClosingConnection)
        c.row_factory = sqlite3.Row
        return c

    def profiles(self):
        with self.connect() as c:
            rows = [dict(x) for x in c.execute('SELECT * FROM profiles ORDER BY id != ?, created', ('my-voice',))]
            details = {x['profile_id']: json.loads(x['data']) for x in c.execute('SELECT * FROM profile_details')}
        return [dict(x, details=details.get(x['id'], {})) for x in rows]

    def profile(self, ident):
        with self.connect() as c:
            row = c.execute('SELECT * FROM profiles WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Voice profile not found.')
        with self.connect() as c:
            details = c.execute('SELECT data FROM profile_details WHERE profile_id=?', (ident,)).fetchone()
        return dict(row, details=json.loads(details['data']) if details else {})

    def save_profile_details(self, ident, details):
        self.profile(ident)
        with self.connect() as c:
            c.execute('INSERT INTO profile_details VALUES (?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data',
                      (ident, json.dumps(details)))

    def create_profile(self, name, kind, authorization):
        ident = uuid.uuid4().hex
        with self.connect() as c:
            c.execute('INSERT INTO profiles (id,name,kind,authorization,created,primary_asset) VALUES (?,?,?,?,?,NULL)',
                      (ident, name, kind, authorization, now()))
        return self.profile(ident)

    def rename(self, ident, name):
        self.profile(ident)
        with self.connect() as c:
            c.execute('UPDATE profiles SET name=? WHERE id=?', (name, ident))

    def assets(self, profile_id=None):
        with self.connect() as c:
            rows = c.execute('SELECT * FROM assets WHERE profile_id=? ORDER BY created DESC', (profile_id,)) if profile_id else c.execute('SELECT * FROM assets ORDER BY created DESC')
            return [self._asset(x) for x in rows]

    def _asset(self, row):
        result = dict(row)
        result['metadata'] = json.loads(result['metadata'])
        return result

    def asset(self, ident):
        with self.connect() as c:
            row = c.execute('SELECT * FROM assets WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Audio not found.')
        return self._asset(row)

    def path(self, ident):
        if not ident or len(ident) != 32 or any(ch not in '0123456789abcdef' for ch in ident):
            raise ValueError('Invalid audio ID.')
        return self.audio / (ident + '.wav')

    def add_asset(self, ident, profile_id, name, kind, metadata):
        self.profile(profile_id)
        with self.connect() as c:
            c.execute('INSERT INTO assets (id,profile_id,name,kind,created,metadata) VALUES (?,?,?,?,?,?)',
                      (ident, profile_id, name, kind, now(), json.dumps(metadata)))
            if kind == 'reference':
                c.execute('UPDATE profiles SET primary_asset=? WHERE id=? AND primary_asset IS NULL', (ident, profile_id))
        return self.asset(ident)

    def set_primary(self, profile_id, asset_id):
        asset = self.asset(asset_id)
        if asset['profile_id'] != profile_id or asset['kind'] != 'reference':
            raise ValueError('Choose a reference belonging to this speaker.')
        with self.connect() as c:
            c.execute('UPDATE profiles SET primary_asset=? WHERE id=?', (asset_id, profile_id))

    def recycle_items(self):
        with self.connect() as c:
            return [dict(id=r['id'], kind=r['kind'], name=json.loads(r['data'])['name'], created=r['created'])
                    for r in c.execute('SELECT * FROM recycle_bin ORDER BY created DESC')]

    def delete_asset(self, ident):
        asset = self.asset(ident)
        with self.connect() as c:
            asset['reviews'] = [dict(r) for r in c.execute('SELECT * FROM reviews WHERE asset_id=?', (ident,))]
            asset['was_primary'] = c.execute('SELECT primary_asset FROM profiles WHERE id=?', (asset['profile_id'],)).fetchone()[0] == ident
            c.execute('INSERT INTO recycle_bin VALUES (?,?,?,?)', (ident, 'asset', json.dumps(asset), now()))
            c.execute('DELETE FROM assets WHERE id=?', (ident,))
            c.execute('DELETE FROM reviews WHERE asset_id=?', (ident,))
            c.execute('UPDATE profiles SET primary_asset=NULL WHERE primary_asset=?', (ident,))
        # Immutable WAV stays in place so project history remains recoverable.

    def delete_profile(self, ident):
        profile = self.profile(ident)
        with self.connect() as c:
            preferences = c.execute('SELECT data FROM voice_preferences WHERE profile_id=?', (ident,)).fetchone()
            profile['preferences'] = preferences['data'] if preferences else None
            profile['assets'] = []
            for asset in self.assets(ident):
                asset['reviews'] = [dict(r) for r in c.execute('SELECT * FROM reviews WHERE asset_id=?', (asset['id'],))]
                profile['assets'].append(asset)
            recovery_id = uuid.uuid4().hex
            c.execute('INSERT INTO recycle_bin VALUES (?,?,?,?)', (recovery_id, 'profile', json.dumps(profile), now()))
            c.execute('DELETE FROM reviews WHERE asset_id IN (SELECT id FROM assets WHERE profile_id=?)', (ident,))
            c.execute('DELETE FROM assets WHERE profile_id=?', (ident,))
            c.execute('DELETE FROM voice_preferences WHERE profile_id=?', (ident,))
            c.execute('DELETE FROM profile_details WHERE profile_id=?', (ident,))
            if ident != 'my-voice':
                c.execute('DELETE FROM profiles WHERE id=?', (ident,))
            else:
                c.execute('UPDATE profiles SET primary_asset=NULL WHERE id=?', (ident,))

    def restore_deleted(self, ident):
        with self.connect() as c:
            row = c.execute('SELECT * FROM recycle_bin WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Recovery item not found.')
            data = json.loads(row['data'])
            assets = data['assets'] if row['kind'] == 'profile' else [data]
            for asset in assets:
                if not self.path(asset['id']).is_file():
                    raise ValueError('Recovery audio is missing. Restore a verified backup.')
                if c.execute('SELECT id FROM assets WHERE id=?', (asset['id'],)).fetchone():
                    raise ValueError('Recording already exists; recovery preserved without changes.')
            profile_id = data['id'] if row['kind'] == 'profile' else data['profile_id']
            existing = c.execute('SELECT * FROM profiles WHERE id=?', (profile_id,)).fetchone()
            if row['kind'] == 'profile':
                if existing and (profile_id != 'my-voice' or c.execute('SELECT id FROM assets WHERE profile_id=?', (profile_id,)).fetchone()):
                    raise ValueError('This profile has new recordings. Back them up before restoring the earlier profile.')
                c.execute('INSERT OR REPLACE INTO profiles (id,name,kind,authorization,created,primary_asset) VALUES (?,?,?,?,?,?)',
                          tuple(data[k] for k in ('id','name','kind','authorization','created','primary_asset')))
                c.execute('INSERT OR REPLACE INTO profile_details VALUES (?,?)', (profile_id, json.dumps(data.get('details', {}))))
                if data.get('preferences'):
                    c.execute('INSERT OR REPLACE INTO voice_preferences VALUES (?,?)', (profile_id, data['preferences']))
            elif not existing:
                raise ValueError('Restore the deleted family profile before restoring this recording.')
            for asset in assets:
                c.execute('INSERT INTO assets (id,profile_id,name,kind,created,metadata) VALUES (?,?,?,?,?,?)',
                          tuple(asset[k] for k in ('id','profile_id','name','kind','created')) + (json.dumps(asset['metadata']),))
                for review in asset.get('reviews', []):
                    c.execute('INSERT INTO reviews (id,asset_id,data,created) VALUES (?,?,?,?)', tuple(review[k] for k in ('id','asset_id','data','created')))
            if row['kind'] == 'asset' and data.get('was_primary') and not existing['primary_asset']:
                c.execute('UPDATE profiles SET primary_asset=? WHERE id=?', (data['id'], profile_id))
            c.execute('DELETE FROM recycle_bin WHERE id=?', (ident,))
        return {'restored': True, 'profile_id': profile_id}

    def settings(self):
        defaults = {'engine': 'chatterbox', 'device': 'auto'}
        with self.connect() as c:
            defaults.update({r['key']: json.loads(r['value']) for r in c.execute('SELECT * FROM settings')})
        return defaults

    def save_settings(self, settings):
        with self.connect() as c:
            for key, val in settings.items():
                c.execute('INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(val)))

    def review(self, ident, data):
        asset = self.asset(ident)
        if asset['kind'] != 'generated':
            raise ValueError('Only generated clips can be evaluated.')
        with self.connect() as c:
            c.execute('INSERT INTO reviews (id,asset_id,data,created) VALUES (?,?,?,?)', (uuid.uuid4().hex, ident, json.dumps(data), now()))

    def reviews(self):
        with self.connect() as c:
            return [dict(r, data=json.loads(r['data'])) for r in c.execute('SELECT * FROM reviews ORDER BY created DESC')]
