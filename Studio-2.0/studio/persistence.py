"""Optional durable storage in the owner's private Hugging Face dataset.
No public repository is accepted; checkpoints are never duplicated here.
"""
import os
from pathlib import Path


class PrivateProfileStore:
    def __init__(self,repository,token):
        from huggingface_hub import HfApi
        if not token:raise RuntimeError('Private durable storage requires STUDIO2_BACKUP_TOKEN.')
        self.repository=repository;self.token=token;self.api=HfApi(token=token)
        info=self.api.repo_info(repository,repo_type='dataset')
        if not info.private:raise RuntimeError('Refusing to store family voice data in a public dataset.')

    def restore(self,families):
        from huggingface_hub import snapshot_download
        snapshot_download(self.repository,repo_type='dataset',token=self.token,local_dir=families,
                          ignore_patterns=['README.md','.gitattributes'])

    def save(self,folder):
        self.api.upload_folder(repo_id=self.repository,repo_type='dataset',folder_path=folder,
                               path_in_repo=folder.name,ignore_patterns=['*.tmp'],
                               commit_message='Save private family profile')

    def delete(self,identity):
        self.api.delete_folder(identity,repo_id=self.repository,repo_type='dataset',commit_message='Remove revoked/deleted profile from active storage')

    def delete_recording(self,identity,asset):
        from huggingface_hub import CommitOperationDelete
        info=self.api.list_repo_files(self.repository,repo_type='dataset')
        paths=[identity+'/references/'+asset,identity+'/original-recordings/'+asset]
        operations=[CommitOperationDelete(path_in_repo=p) for p in paths if p in info]
        if operations:self.api.create_commit(self.repository,repo_type='dataset',operations=operations,commit_message='Remove deleted reference from active storage')
