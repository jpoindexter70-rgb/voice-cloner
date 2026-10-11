import hashlib
import io
import json
import zipfile

import pytest

from studio import model_archive


def test_import_rejects_self_signed_hash_manifest_without_replacing_existing_model(tmp_path,monkeypatch):
    # Independent trusted hashes are injected for a small fixture; self-reported hashes are insufficient.
    approved={'repository':'ResembleAI/chatterbox','revision':'approved-revision','files':{
        've.safetensors':{'sha256':hashlib.sha256(b'official').hexdigest()}}}
    # Patch only the metadata reader; leave file handling real.
    registry=tmp_path/'model-revisions.json';registry.write_text(json.dumps({'chatterbox':approved}))
    monkeypatch.setattr(model_archive,'__file__',str(tmp_path/'model_archive.py'))
    dest=tmp_path/'models'/'chatterbox';dest.mkdir(parents=True);(dest/'keep.txt').write_text('existing')
    data=io.BytesIO()
    manifest={'repository':approved['repository'],'revision':approved['revision'],'files':{
        've.safetensors':{'sha256':hashlib.sha256(b'forged').hexdigest(),'size':6}}}
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest));z.writestr('ve.safetensors',b'forged')
    data.seek(0)
    with pytest.raises(ValueError,match='independently pinned upstream hash'):
        model_archive.import_archive(data,dest,'chatterbox')
    assert (dest/'keep.txt').read_text()=='existing'


def test_official_archive_import_preserves_previous_model_directory(tmp_path,monkeypatch):
    from studio.engine import MODELS
    contents={name:b'fixture-'+name.encode() for name in MODELS['chatterbox']['files']}
    approved={'repository':'ResembleAI/chatterbox','revision':'fixture-official',
              'files':{name:{'sha256':hashlib.sha256(data).hexdigest()} for name,data in contents.items()}}
    (tmp_path/'model-revisions.json').write_text(json.dumps({'chatterbox':approved}))
    monkeypatch.setattr(model_archive,'__file__',str(tmp_path/'model_archive.py'))
    manifest={**approved,'files':{name:{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)} for name,data in contents.items()}}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest))
        for name,data in contents.items():z.writestr(name,data)
    archive.seek(0)
    destination=tmp_path/'models'/'chatterbox';destination.mkdir(parents=True);(destination/'old.txt').write_text('preserve')
    result=model_archive.import_archive(archive,destination,'chatterbox')
    from pathlib import Path
    assert (Path(result['preserved_previous_model'])/'old.txt').read_text()=='preserve'
    assert (destination/'ve.safetensors').read_bytes()==contents['ve.safetensors']


def test_import_rejects_archive_paths_and_unsupported_revision(tmp_path,monkeypatch):
    registry=tmp_path/'model-revisions.json';registry.write_text(json.dumps({'chatterbox':{
        'repository':'ResembleAI/chatterbox','revision':'approved','files':{'file.pt':{'sha256':'hash'}}}}))
    monkeypatch.setattr(model_archive,'__file__',str(tmp_path/'model_archive.py'))
    malicious=io.BytesIO()
    with zipfile.ZipFile(malicious,'w') as z:z.writestr('../outside.pt',b'bad');z.writestr('manifest.json','{}')
    malicious.seek(0)
    with pytest.raises(ValueError,match='complete model ZIP'):
        model_archive.import_archive(malicious,tmp_path/'models'/'chatterbox','chatterbox')
    wrong=io.BytesIO()
    with zipfile.ZipFile(wrong,'w') as z:
        z.writestr('file.pt',b'bad');z.writestr('manifest.json',json.dumps({'repository':'ResembleAI/chatterbox','revision':'unsupported'}))
    wrong.seek(0)
    with pytest.raises(ValueError,match='supported official model revision'):
        model_archive.import_archive(wrong,tmp_path/'models'/'chatterbox','chatterbox')
