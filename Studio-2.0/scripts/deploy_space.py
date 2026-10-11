"""Publish only the new app to a private, free-CPU Hugging Face Docker Space.
Credentials must be supplied securely; this script never prints their values.
"""
import os
import tempfile
import json
from pathlib import Path
from huggingface_hub import HfApi


def main():
    token=os.getenv('HF_DEPLOY_TOKEN')
    password=os.getenv('STUDIO2_HOST_PASSWORD')
    if not token or not password:
        raise RuntimeError('Add HF_DEPLOY_TOKEN and STUDIO2_HOST_PASSWORD securely in environment settings; never paste them into chat.')
    if len(password)<16:
        raise RuntimeError('The hosted studio password must contain at least 16 characters.')
    api=HfApi(token=token)
    account=api.whoami()['name']
    repo=account+'/ai-voice-cloning-studio-2'
    # No paid hardware request. Existing Spaces are preserved rather than overwritten silently.
    dataset=account+'/studio2-private-family-data'
    source=Path(__file__).resolve().parents[1]
    state_path=source/'.runtime/deployment.json'
    state_path.parent.mkdir(parents=True,exist_ok=True)
    state=json.loads(state_path.read_text()) if state_path.exists() else {'account':account,'dataset_created':False,'space_created':False}
    if state['account']!=account:raise RuntimeError('Deployment state belongs to another account; refusing to modify its resources.')
    if not state['dataset_created']:
        api.create_repo(dataset,repo_type='dataset',private=True,exist_ok=False)
        state['dataset_created']=True;state_path.write_text(json.dumps(state))
    if not state['space_created']:
        api.create_repo(repo,repo_type='space',space_sdk='docker',private=True,exist_ok=False)
        state['space_created']=True;state_path.write_text(json.dumps(state))
    if not api.repo_info(dataset,repo_type='dataset').private or not api.space_info(repo).private:
        raise RuntimeError('Deployment repositories must remain private.')
    host=api.space_info(repo).host
    if not host:raise RuntimeError('Space hostname is not available yet; retry after provisioning.')
    origin=host if host.startswith('https://') else 'https://'+host
    api.add_space_secret(repo,'STUDIO2_PASSWORD',password)
    api.add_space_secret(repo,'STUDIO2_BACKUP_TOKEN',token)
    api.add_space_variable(repo,'STUDIO2_BACKUP_REPO',dataset)
    api.add_space_variable(repo,'STUDIO2_PUBLIC_ORIGIN',origin)
    source=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temp:
        import shutil
        target=Path(temp)
        shutil.copytree(source/'studio',target/'studio',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ['Dockerfile','requirements.txt','requirements-dev.txt','requirements-engine.txt','requirements-engine-lock.txt']:
            shutil.copy2(source/name,target/name)
        (target/'README.md').write_text('---\ntitle: AI Voice Cloning Studio 2.0\nsdk: docker\napp_port: 7860\n---\nPrivate family voice studio. Shared models download automatically; personal profiles remain separate.\nProfiles are mirrored into a separate private dataset for restoration after restarts. Historical dataset versions remain private backups, not forensic erasure.\n')
        api.upload_folder(repo_id=repo,repo_type='space',folder_path=target,commit_message='Deploy independent Studio 2.0 browser app')
    print('Private Space created:', 'https://huggingface.co/spaces/'+repo)
    state.update(origin=origin,uploaded=True);state_path.write_text(json.dumps(state))
    print('Deployment is building; verify the actual app before calling it ready.')


if __name__=='__main__':main()
