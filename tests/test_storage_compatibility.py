"""Upgrade regression fixtures, not assumptions about the user's unknown schema."""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from studio.app import create_app
from studio.storage import Store


def test_eight_column_profiles_preserve_existing_data_and_support_all_writes(tmp_path):
    root = tmp_path / 'data'
    store = Store(root)
    existing = store.create_profile('Existing speaker', 'adult', 'Authorized')
    ident = 'a' * 32
    store.path(ident).write_bytes(b'preserved reference fixture')
    store.add_asset(ident, existing['id'], 'Existing recording', 'reference', {'seconds': 10})
    with store.connect() as c:
        c.execute('ALTER TABLE profiles ADD COLUMN old_notes TEXT')
        c.execute("ALTER TABLE profiles ADD COLUMN old_version INTEGER NOT NULL DEFAULT 7")
        c.execute('ALTER TABLE assets ADD COLUMN old_notes TEXT')
        c.execute('ALTER TABLE settings ADD COLUMN old_notes TEXT')
        c.execute('ALTER TABLE reviews ADD COLUMN old_notes TEXT')
        c.execute("INSERT INTO settings(key,value,old_notes) VALUES ('device','\"cpu\"','retain me')")
    # The exact six-values/eight-columns failure reported by the user.
    with store.connect() as c:
        with pytest.raises(sqlite3.OperationalError, match='8 columns but 6 values'):
            c.execute("INSERT OR IGNORE INTO profiles VALUES ('my-voice','My Voice','self','Own voice','today',NULL)")
    restarted = Store(root)
    assert restarted.db == root / 'studio.sqlite3'
    assert restarted.profile(existing['id'])['primary_asset'] == ident
    assert restarted.path(ident).read_bytes() == b'preserved reference fixture'
    added = restarted.create_profile('New speaker', 'adult', 'Authorized')
    generated = 'b' * 32
    restarted.path(generated).write_bytes(b'generated fixture')
    restarted.add_asset(generated, added['id'], 'Output', 'generated', {'synthetic': True})
    restarted.review(generated, {'similarity': 3})
    restarted.save_settings({'device': 'auto'})
    with restarted.connect() as c:
        assert c.execute("SELECT old_notes FROM settings WHERE key='device'").fetchone()[0] == 'retain me'
    assert len(restarted.reviews()) == 1
    restarted.delete_profile(added['id'])
    assert restarted.reviews() == []
    assert restarted.asset(ident)['profile_id'] == existing['id']
    assert Store(root).profile(existing['id'])['primary_asset'] == ident
    # Exercise the installer command against this persisted eight-column database.
    result = subprocess.run([sys.executable, '-m', 'studio.cli', 'doctor'],
        env={**os.environ, 'VCR_DATA_DIR': str(root)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['database'] == str(root / 'studio.sqlite3')


@pytest.mark.parametrize('definition', [
    'id TEXT PRIMARY KEY, name TEXT, engine TEXT, reference TEXT, consent TEXT, created TEXT, notes TEXT, version TEXT',
    'id TEXT PRIMARY KEY, name TEXT, kind TEXT, authorization TEXT, created TEXT, primary_asset TEXT, required_legacy TEXT NOT NULL, notes TEXT',
])
def test_unknown_or_required_legacy_columns_are_preserved_without_modification(tmp_path, definition):
    db = tmp_path / 'studio.sqlite3'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE profiles (' + definition + ')')
        c.execute('CREATE TABLE legacy_private_data (value TEXT)')
        c.execute("INSERT INTO legacy_private_data VALUES ('keep every byte')")
    before = db.read_bytes()
    with pytest.warns(RuntimeWarning, match='preserved separately'):
        store = Store(tmp_path)
    assert db.read_bytes() == before
    assert store.db.name == 'studio-v1.sqlite3'
    added = store.create_profile('Persistent new speaker', 'adult', 'Authorized')
    with pytest.warns(RuntimeWarning):
        again = Store(tmp_path)
    assert again.profile(added['id'])['name'] == 'Persistent new speaker'
    assert db.read_bytes() == before
    with pytest.warns(RuntimeWarning):
        app = create_app(tmp_path)
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert len(client.get('/api/profiles').json()) == 2
        diagnostics = client.get('/api/diagnostics').json()
        assert diagnostics['preserved_earlier_database'] == str(db)


def test_reordered_columns_do_not_change_identity_or_reference(tmp_path):
    with sqlite3.connect(tmp_path / 'studio.sqlite3') as c:
        c.execute('CREATE TABLE profiles (primary_asset TEXT, created TEXT NOT NULL, authorization TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, id TEXT PRIMARY KEY, extra TEXT, extra2 TEXT)')
    store = Store(tmp_path)
    assert store.profile('my-voice')['kind'] == 'self'
    profile = store.create_profile('Speaker', 'child', 'Parent permission')
    assert profile['name'] == 'Speaker' and profile['primary_asset'] is None


def test_incompatible_dedicated_database_stops_without_changing_either_file(tmp_path):
    for name in ['studio.sqlite3', 'studio-v1.sqlite3']:
        with sqlite3.connect(tmp_path / name) as c:
            c.execute('CREATE TABLE profiles (unknown TEXT)')
    before = {path: path.read_bytes() for path in tmp_path.glob('*.sqlite3')}
    with pytest.raises(RuntimeError, match='Both databases were preserved'):
        Store(tmp_path)
    assert all(path.read_bytes() == content for path, content in before.items())


def test_connections_close_and_failed_transactions_rollback(tmp_path):
    import sqlite3
    import pytest
    store = Store(tmp_path / 'closed-handles')
    with store.connect() as connection:
        connection.execute("INSERT INTO settings(key,value) VALUES ('closed-test','1')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with store.connect() as failed:
            failed.execute("UPDATE settings SET value='2' WHERE key='closed-test'")
            raise RuntimeError('Interrupted operation')
    with pytest.raises(sqlite3.ProgrammingError):
        failed.execute('SELECT 1')
    with store.connect() as check:
        assert check.execute("SELECT value FROM settings WHERE key='closed-test'").fetchone()[0] == '1'
