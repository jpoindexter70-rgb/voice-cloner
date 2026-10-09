"""Backup regression tests for the missing-file failure reported on Windows."""
import zipfile
from pathlib import Path
import pytest
from scripts import backup_existing as backup


def test_missing_dependency_refreshes_inventory_without_losing_recording(tmp_path,monkeypatch,capsys):
    source=tmp_path/'legacy';source.mkdir()
    recording=source/'voice.wav';recording.write_bytes(b'personal reference fixture')
    dependency=source/'dependency.py';dependency.write_bytes(b'old package')
    real_open=Path.open
    disappeared=False
    def open_file(path,mode='r',*args,**kwargs):
        nonlocal disappeared
        if path==dependency and mode=='rb' and not disappeared:
            disappeared=True
            dependency.unlink()  # Simulate another installer removing an old package file.
            raise FileNotFoundError(2,'File disappeared during backup',str(path))
        return real_open(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,'open',open_file)
    destination=tmp_path/'backups'
    result=backup.backup(source,destination)
    with zipfile.ZipFile(result) as archive:
        assert archive.read('voice.wav')==b'personal reference fixture'
        assert archive.testzip() is None
    assert recording.read_bytes()==b'personal reference fixture'
    assert list(destination.glob('*.incomplete.zip'))
    output=capsys.readouterr().out
    assert 'SOURCE CHANGED OR DISAPPEARED' in output
    assert 'retrying once' in output
    assert output.count('VERIFIED BACKUP:')==1


def test_continuously_changing_file_stops_without_claiming_verified_backup(tmp_path,monkeypatch,capsys):
    source=tmp_path/'legacy';source.mkdir()
    changing=source/'dependency.py';changing.write_bytes(b'package')
    reference=source/'voice.wav';reference.write_bytes(b'keep this reference')
    real_open=zipfile.ZipFile.open
    def archive_open(archive,name,mode='r',*args,**kwargs):
        if mode=='w' and name.filename=='dependency.py':
            with changing.open('ab') as f:f.write(b'updated by concurrent process')
        return real_open(archive,name,mode,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,'open',archive_open)
    destination=tmp_path/'backups'
    with pytest.raises(RuntimeError,match='stable source files'):
        backup.backup(source,destination)
    assert reference.read_bytes()==b'keep this reference'
    assert len(list(destination.glob('*.incomplete.zip')))==2
    assert 'VERIFIED BACKUP:' not in capsys.readouterr().out
    assert not [p for p in destination.glob('*.zip') if not p.name.endswith('.incomplete.zip')]


def test_resume_rechecks_archive_without_copying_or_changing_current_files(tmp_path,capsys):
    source=tmp_path/'VoiceControlRoom';source.mkdir()
    reference=source/'voice.wav';reference.write_bytes(b'saved reference')
    destination=tmp_path/'backups'
    result=backup.backup(source,destination)
    (destination/'VoiceControlRoom-99999999.incomplete.zip').write_bytes(b'not a verified archive')
    before=result.read_bytes()
    reference.write_bytes(b'a new reference recorded after the backup')
    checked=backup.verify_existing(source,destination)
    assert checked==result and result.read_bytes()==before
    assert reference.read_bytes()==b'a new reference recorded after the backup'
    assert len(list(destination.glob('*.zip')))==2
    assert 'not files changed since that backup' in capsys.readouterr().out


def test_resume_rejects_missing_or_corrupt_archives(tmp_path):
    source=tmp_path/'VoiceControlRoom';source.mkdir();(source/'voice.wav').write_bytes(b'preserve')
    destination=tmp_path/'backups';destination.mkdir()
    with pytest.raises(RuntimeError,match='No previous backup'):
        backup.verify_existing(source,destination)
    (destination/'VoiceControlRoom-20261009.zip').write_bytes(b'corrupt')
    with pytest.raises(zipfile.BadZipFile):
        backup.verify_existing(source,destination)
    assert (source/'voice.wav').read_bytes()==b'preserve'
