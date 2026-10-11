"""Verified official checkpoints; no recording data ever leaves this downloader."""
import hashlib
import json
import os
import urllib.request
from pathlib import Path

SPECS = {
    'expressive': {'repository': 'ResembleAI/chatterbox', 'files': ['ve.safetensors','t3_cfg.safetensors','s3gen.safetensors','tokenizer.json','conds.pt']},
    'turbo': {'repository': 'ResembleAI/chatterbox-turbo', 'files': ['ve.safetensors','t3_turbo_v1.safetensors','s3gen_meanflow.safetensors','tokenizer_config.json','special_tokens_map.json','added_tokens.json','merges.txt','vocab.json','conds.pt']},
}

SPECS['expressive']['revision']='5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18'
SPECS['turbo']['revision']='749d1c1a46eb10492095d68fbcf55691ccf137cd'


def sha256(path):
    value=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def download(root, name, spec=None):
    spec=spec or SPECS[name]; root=Path(root); target=root/name; target.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen('https://huggingface.co/api/models/'+spec['repository']+('/revision/'+spec['revision'] if spec.get('revision') else '')+'?blobs=true',timeout=30) as response:
        meta=json.load(response)
    manifest={'repository':spec['repository'],'revision':meta['sha'],'files':{}}
    upstream={f['rfilename']:f for f in meta['siblings']}
    for filename in spec['files']:
        item=upstream[filename]; path=target/filename
        expected=(item.get('lfs') or {}).get('sha256')
        valid=path.exists() and path.stat().st_size==item['size'] and (sha256(path)==expected if expected else hashlib.sha1(b'blob '+str(item['size']).encode()+b'\0'+path.read_bytes()).hexdigest()==item['blobId'])
        if not valid:
            temporary=path.with_suffix(path.suffix+'.download')
            url='https://huggingface.co/'+spec['repository']+'/resolve/'+meta['sha']+'/'+filename
            print('Downloading',name,filename,'bytes',item['size'],flush=True)
            # Official transfer client supports parallel content-addressed downloads.
            from huggingface_hub import hf_hub_download
            downloaded=Path(hf_hub_download(spec['repository'], filename, revision=meta['sha'], local_dir=target, force_download=True))
            if downloaded != temporary:
                downloaded.replace(temporary)
            if temporary.stat().st_size!=item['size']:raise RuntimeError('Incomplete checkpoint: '+filename)
            actual=sha256(temporary)
            if expected and actual!=expected:raise RuntimeError('Checkpoint checksum mismatch: '+filename)
            if not expected and hashlib.sha1(b'blob '+str(item['size']).encode()+b'\0'+temporary.read_bytes()).hexdigest()!=item['blobId']:raise RuntimeError('Checkpoint Git hash mismatch: '+filename)
            temporary.replace(path)
        manifest['files'][filename]={'sha256':sha256(path),'size':path.stat().st_size}
        print('Verified',name,filename,flush=True)
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def verify(root,name,spec=None):
    spec=spec or SPECS[name]
    path=Path(root)/name
    manifest=json.loads((path/'manifest.json').read_text())
    if spec.get('revision') and manifest['revision']!=spec['revision']:raise RuntimeError('Wrong checkpoint revision')
    if manifest['repository']!=spec['repository']:raise RuntimeError('Wrong checkpoint repository')
    for filename in spec['files']:
        expected=manifest['files'][filename]; actual=path/filename
        if actual.stat().st_size!=expected['size'] or sha256(actual)!=expected['sha256']:raise RuntimeError('Checkpoint integrity failed: '+filename)
    return path


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['download','verify']);parser.add_argument('--root',required=True);parser.add_argument('--engine',choices=[*SPECS,'all'],default='all');args=parser.parse_args()
    for name in (SPECS if args.engine=='all' else [args.engine]):
        (download if args.command=='download' else verify)(args.root,name)
