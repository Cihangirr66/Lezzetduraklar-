# -*- coding: utf-8 -*-
import json
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


def _firebase_admin():
    try:
        import firebase_admin
        from firebase_admin import auth, credentials, db, firestore, storage
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'firebase-admin paketi yüklü değil. `pip install firebase-admin` komutunu çalıştırın.'
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
            raise ValueError('FIREBASE_CREDENTIALS_JSON geçerli bir JSON değil.') from exc
        return credentials.Certificate(service_account)

    credentials_path = _credentials_path()
    if not credentials_path.exists():
        raise FileNotFoundError(
            'Firebase servis hesabı bulunamadı. '
            f'Dosya beklenen yer: {credentials_path}. '
            'Alternatif olarak FIREBASE_CREDENTIALS_JSON ortam değişkenini kullanabilirsiniz.'
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


class FirebaseIdentityError(RuntimeError):
    pass


class FirebaseTransportError(FirebaseIdentityError):
    pass


def _identity_toolkit_url(method):
    api_key = getattr(settings, 'FIREBASE_WEB_API_KEY', '')
    if not api_key:
        raise FirebaseIdentityError(
            'FIREBASE_WEB_API_KEY tanımlı değil. Firebase Auth web API anahtarını `.env` dosyasına ekleyin.'
        )
    return f'https://identitytoolkit.googleapis.com/v1/accounts:{method}?key={api_key}'


def _identity_toolkit_request(method, payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = Request(
        _identity_toolkit_url(method),
        data=data,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='ignore')
        try:
            error_payload = json.loads(body)
            message = error_payload.get('error', {}).get('message') or body
        except json.JSONDecodeError:
            message = body or str(exc)
        raise FirebaseIdentityError(message) from exc
    except URLError as exc:
        raise FirebaseTransportError(f'Firebase bağlantı hatası: {exc.reason}') from exc


def send_password_reset_email(email):
    return _identity_toolkit_request(
        'sendOobCode',
        {
            'requestType': 'PASSWORD_RESET',
            'email': email,
        },
    )


def verify_email_password(email, password):
    return _identity_toolkit_request(
        'signInWithPassword',
        {
            'email': email,
            'password': password,
            'returnSecureToken': True,
        },
    )


def generate_password_reset_link(email):
    auth = get_auth_client()
    return auth.generate_password_reset_link(email)
