from django.core.files.base import ContentFile
from django.core.files.storage import Storage

from .firebase import get_storage_bucket


class FirebaseStorage(Storage):
    def _open(self, name, mode='rb'):
        blob = get_storage_bucket().blob(name)
        return ContentFile(blob.download_as_bytes(), name=name)

    def _save(self, name, content):
        blob = get_storage_bucket().blob(name)
        blob.upload_from_file(content.file, content_type=getattr(content, 'content_type', None))
        return name

    def delete(self, name):
        blob = get_storage_bucket().blob(name)
        if blob.exists():
            blob.delete()

    def exists(self, name):
        return get_storage_bucket().blob(name).exists()

    def url(self, name):
        blob = get_storage_bucket().blob(name)
        return blob.public_url
