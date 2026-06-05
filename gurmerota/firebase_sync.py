# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime, time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User

from lezzetduraklari.firebase import get_auth_client, get_firestore_client

from .models import Favori, Kategori, Mekan, MekanFoto, Yorum

logger = logging.getLogger(__name__)


COLLECTIONS = {
    User: 'users',
    Kategori: 'kategoriler',
    Mekan: 'mekanlar',
    MekanFoto: 'mekan_fotograflari',
    Yorum: 'yorumlar',
    Favori: 'favoriler',
}


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    return value


def _file_payload(file_field):
    if not file_field:
        return {'name': '', 'url': ''}
    try:
        url = file_field.url
    except Exception:
        url = ''
    return {'name': file_field.name, 'url': url}


def _doc_id(instance):
    return str(instance.pk)


def serialize_user(user):
    return {
        'id': user.pk,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': _value(user.date_joined),
        'last_login': _value(user.last_login),
        'firebase_uid': firebase_uid_for_user(user),
    }


def serialize_kategori(kategori):
    return {
        'id': kategori.pk,
        'isim': kategori.isim,
        'ikon_slug': kategori.ikon_slug,
    }


def serialize_mekan(mekan):
    return {
        'id': mekan.pk,
        'isim': mekan.isim,
        'aciklama': mekan.aciklama,
        'kategori_id': mekan.kategori_id,
        'kategori_adi': mekan.kategori.isim if mekan.kategori_id else '',
        'adres': mekan.adres,
        'latitude': _value(mekan.latitude),
        'longitude': _value(mekan.longitude),
        'telefon': mekan.telefon,
        'web_sitesi': mekan.web_sitesi,
        'calisma_baslangic': _value(mekan.calisma_baslangic),
        'calisma_bitis': _value(mekan.calisma_bitis),
        'calisma_gunleri': mekan.calisma_gunleri,
        'kapak_fotografi': _file_payload(mekan.kapak_fotografi),
        'olusturulma_tarihi': _value(mekan.olusturulma_tarihi),
        'ortalama_puan': _value(mekan.ortalama_puan),
        'google_maps_url': mekan.google_maps_url,
    }


def serialize_mekan_foto(foto):
    return {
        'id': foto.pk,
        'mekan_id': foto.mekan_id,
        'image': _file_payload(foto.image),
        'sira': foto.sira,
        'olusturulma_tarihi': _value(foto.olusturulma_tarihi),
    }


def serialize_yorum(yorum):
    return {
        'id': yorum.pk,
        'mekan_id': yorum.mekan_id,
        'kullanici_id': yorum.kullanici_id,
        'kullanici_adi': yorum.kullanici.username if yorum.kullanici_id else '',
        'yorum': yorum.yorum,
        'puan': yorum.puan,
        'olusturulma_tarihi': _value(yorum.olusturulma_tarihi),
    }


def serialize_favori(favori):
    return {
        'id': favori.pk,
        'kullanici_id': favori.kullanici_id,
        'mekan_id': favori.mekan_id,
        'olusturulma_tarihi': _value(favori.olusturulma_tarihi),
    }


SERIALIZERS = {
    User: serialize_user,
    Kategori: serialize_kategori,
    Mekan: serialize_mekan,
    MekanFoto: serialize_mekan_foto,
    Yorum: serialize_yorum,
    Favori: serialize_favori,
}


def firebase_uid_for_user(user):
    return f'django-user-{user.pk}'


def sync_enabled():
    return bool(getattr(settings, 'FIREBASE_SYNC_ENABLED', False))


def sync_instance(instance):
    if not sync_enabled():
        return
    collection = COLLECTIONS.get(type(instance))
    serializer = SERIALIZERS.get(type(instance))
    if not collection or not serializer:
        return
    payload = serializer(instance)
    get_firestore_client().collection(collection).document(_doc_id(instance)).set(payload)


def delete_instance(instance):
    if not sync_enabled() or not instance.pk:
        return
    collection = COLLECTIONS.get(type(instance))
    if collection:
        get_firestore_client().collection(collection).document(_doc_id(instance)).delete()


def safe_sync_instance(instance):
    try:
        sync_instance(instance)
    except Exception:
        logger.exception('Firebase sync failed for %s:%s', type(instance).__name__, instance.pk)


def safe_delete_instance(instance):
    try:
        delete_instance(instance)
    except Exception:
        logger.exception('Firebase delete failed for %s:%s', type(instance).__name__, instance.pk)


def create_or_update_firebase_user(user, password=None):
    if not getattr(settings, 'FIREBASE_AUTH_ENABLED', False):
        safe_sync_instance(user)
        return
    try:
        auth = get_auth_client()
        uid = firebase_uid_for_user(user)
        payload = {
            'uid': uid,
            'display_name': user.get_full_name() or user.username,
            'disabled': not user.is_active,
        }
        if user.email:
            payload['email'] = user.email
            payload['email_verified'] = False
        if password:
            payload['password'] = password
        try:
            auth.create_user(**payload)
        except Exception:
            update_payload = {key: value for key, value in payload.items() if key != 'uid'}
            if update_payload:
                auth.update_user(uid, **update_payload)
        safe_sync_instance(user)
    except Exception:
        logger.warning('Firebase Auth sync failed for user:%s', user.pk)
