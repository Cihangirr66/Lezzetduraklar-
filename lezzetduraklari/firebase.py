import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


def _firebase_admin():
    try:
        import firebase_admin
        from firebase_admin import auth, credentials, db, firestore, storage
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'firebase-admin paketi yuklu degil. `pip install firebase-admin` komutunu calistirin.'
        ) from exc

    return firebase_admin, auth, credentials, db, firestore, storage


def _credentials_path():
    path = Path(settings.FIREBASE_CREDENTIALS_PATH)
    if not path.is_absolute():
        path = settings.BASE_DIR / path
    return path


def _firebase_credential(credentials):
    if settings.FIREBASE_CREDENTIALS_JSON:
        try:
            service_account = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        except json.JSONDecodeError as exc:
            raise ValueError('FIREBASE_CREDENTIALS_JSON gecerli bir JSON degil.') from exc
        return credentials.Certificate(service_account)

    credentials_path = _credentials_path()
    if not credentials_path.exists():
        raise FileNotFoundError(
            'Firebase servis hesabi bulunamadi. '
            f'Dosya beklenen yer: {credentials_path}. '
            'Alternatif olarak FIREBASE_CREDENTIALS_JSON ortam degiskenini kullanabilirsiniz.'
        )

    return credentials.Certificate(str(credentials_path))


@lru_cache(maxsize=1)
def get_firebase_app():
    firebase_admin, _auth, credentials, _db, _firestore, _storage = _firebase_admin()

    if firebase_admin._apps:
        return firebase_admin.get_app()

    options = {}
    if settings.FIREBASE_DATABASE_URL:
        options['databaseURL'] = settings.FIREBASE_DATABASE_URL
    if settings.FIREBASE_STORAGE_BUCKET:
        options['storageBucket'] = settings.FIREBASE_STORAGE_BUCKET

    credential = _firebase_credential(credentials)
    return firebase_admin.initialize_app(credential, options)


def get_firestore_client():
    _admin, _auth, _credentials, _db, firestore, _storage = _firebase_admin()
    get_firebase_app()
    return firestore.client()


def get_auth_client():
    _admin, auth, _credentials, _db, _firestore, _storage = _firebase_admin()
    get_firebase_app()
    return auth


def get_realtime_database_reference(path='/'):
    _admin, _auth, _credentials, db, _firestore, _storage = _firebase_admin()
    get_firebase_app()
    return db.reference(path)


def get_storage_bucket():
    _admin, _auth, _credentials, _db, _firestore, storage = _firebase_admin()
    get_firebase_app()
    if settings.FIREBASE_STORAGE_BUCKET:
        return storage.bucket(settings.FIREBASE_STORAGE_BUCKET)
    return storage.bucket()
