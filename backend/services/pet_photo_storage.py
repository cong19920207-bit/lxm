"""Private, immutable OSS photo objects. No image payload is stored in SQL."""
import os,re
from uuid import UUID
from hashlib import sha256
from backend import config

class PhotoStorageError(ValueError):pass

class PhotoStorage:
    def __init__(self,bucket,bucket_name,namespace):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',namespace):raise PhotoStorageError('storage_configuration')
        self.bucket=bucket;self.bucket_name=bucket_name;self.namespace=namespace
        self.prefix='pet/photos/'+namespace+'/'

    def object_key(self,pet_id,photo_id,digest,mime):
        try:UUID(pet_id);UUID(photo_id)
        except (ValueError,TypeError,AttributeError):raise PhotoStorageError('photo_identity_invalid') from None
        if not re.fullmatch(r'[0-9a-f]{64}',digest) or mime not in {'image/jpeg','image/png'}:raise PhotoStorageError('invalid_photo')
        return f'{self.prefix}{pet_id}/{photo_id}/{digest}.'+('jpg' if mime=='image/jpeg' else 'png')

    def own(self,key):
        if not isinstance(key,str) or not key.startswith(self.prefix) or not re.fullmatch(r'pet/photos/[a-zA-Z0-9_-]{1,40}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f]{64}\.(jpg|png)',key):raise PhotoStorageError('photo_object_not_owned')
        return key

    def head(self,key,digest,size):
        self.own(key)
        try:head=self.bucket.head_object(key)
        except Exception as error:
            if getattr(error,'status',None)==404:return False
            raise PhotoStorageError('storage_unknown') from None
        if head.content_length!=size or head.headers.get('x-oss-meta-pet-sha256')!=digest:raise PhotoStorageError('photo_object_mismatch')
        try:
            if self.bucket.get_object_acl(key).acl!='private':raise PhotoStorageError('photo_object_not_private')
        except PhotoStorageError:raise
        except Exception as error:
            if getattr(error,'status',None)!=403 or getattr(error,'code',None)!='AccessDenied':raise PhotoStorageError('storage_unknown') from None
            # Some existing RAM policies allow private PutObject/GetObject but omit
            # GetObjectAcl. Keep explicit private PUT and prove anonymous access is denied.
            import httpx
            try:status=httpx.head(self.url(key).split('?',1)[0],timeout=15,trust_env=False).status_code
            except Exception:raise PhotoStorageError('storage_unknown') from None
            if status!=403:raise PhotoStorageError('photo_object_not_private')
        return True

    def put_verified(self,key,data,digest,mime):
        self.own(key)
        if sha256(data).hexdigest()!=digest:raise PhotoStorageError('photo_object_mismatch')
        headers={'Content-Type':mime,'Cache-Control':'private, no-store','x-oss-object-acl':'private',
                 'x-oss-forbid-overwrite':'true','x-oss-meta-pet-sha256':digest}
        try:self.bucket.put_object(key,data,headers=headers)
        except Exception:pass  # Reconcile the same immutable key after a lost PUT receipt.
        if not self.head(key,digest,len(data)):raise PhotoStorageError('storage_unknown')

    def url(self,key):
        self.own(key)
        try:
            value=self.bucket.sign_url('GET',key,300,slash_safe=True)
            if not value.startswith('https://'):raise PhotoStorageError('storage_configuration')
            return value
        except PhotoStorageError:raise
        except Exception:raise PhotoStorageError('storage_unavailable') from None

    def delete(self,key):
        self.own(key)
        try:self.bucket.delete_object(key)
        except Exception:pass
        try:self.bucket.head_object(key)
        except Exception as error:
            if getattr(error,'status',None)==404:return
            raise PhotoStorageError('storage_unknown') from None
        raise PhotoStorageError('photo_delete_unconfirmed')


def storage():
    import oss2
    name=os.getenv('PET_PHOTO_OSS_BUCKET') or config.get_oss_bucket()
    endpoint=os.getenv('PET_PHOTO_OSS_ENDPOINT') or config.get_oss_endpoint()
    access=config.get_oss_access_key_id();secret=config.get_oss_access_key_secret()
    if not all((name,endpoint,access,secret)):raise PhotoStorageError('storage_unavailable')
    endpoint=endpoint.strip()
    if not endpoint.startswith(('http://','https://')):endpoint='https://'+endpoint
    if not endpoint.startswith('https://') or '@' in endpoint or '?' in endpoint:raise PhotoStorageError('storage_configuration')
    return PhotoStorage(oss2.Bucket(oss2.Auth(access,secret),endpoint,name,connect_timeout=15),name,os.getenv('PET_PHOTO_NAMESPACE','production'))
