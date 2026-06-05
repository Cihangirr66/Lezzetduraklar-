# -*- coding: utf-8 -*-
from datetime import time
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_time

from gurmerota.models import Favori, Kategori, Mekan, MekanFoto, Yorum
from gurmerota.text_utils import repair_turkish_text
from lezzetduraklari.firebase import get_firestore_client


def _as_decimal(value, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _as_time(value):
    if not value:
        return None
    if isinstance(value, time):
        return value
    parsed = parse_time(str(value))
    return parsed


def _load_json_with_utf8_fallbacks(path):
    encodings = ("utf-8", "utf-8-sig", "latin-1")
    last_error = None
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as handle:
                return json.load(handle)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Desteklenen encoding ile dosya okunamadı.")


class Command(BaseCommand):
    help = "Firebase Firestore/JSON verilerini SQLite'a aktarır."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Aktarımdan önce kategori ve mekan tablolarını temizler.",
        )
        parser.add_argument(
            "--from-json",
            default="data.json",
            help="Firestore bağlantısı yoksa bu fixture dosyasından aktarım yapar (varsayılan: data.json).",
        )
        parser.add_argument(
            "--json-only",
            action="store_true",
            help="Firestore'a hiç bağlanmadan doğrudan JSON dosyasından aktarım yapar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Import sırasında post_save sinyalleri tekrar Firebase'e yazmaya çalışmasın.
        settings.FIREBASE_SYNC_ENABLED = False
        payload = {}
        used_json_fallback = False
        try:
            if options["json_only"]:
                raise RuntimeError("json-only modu")
            client = get_firestore_client()
            payload = {
                "users": list(client.collection("users").stream()),
                "kategoriler": list(client.collection("kategoriler").stream()),
                "mekanlar": list(client.collection("mekanlar").stream()),
                "mekan_fotograflari": list(client.collection("mekan_fotograflari").stream()),
                "yorumlar": list(client.collection("yorumlar").stream()),
                "favoriler": list(client.collection("favoriler").stream()),
            }
        except Exception as exc:
            used_json_fallback = True
            self.stdout.write(self.style.WARNING(f"Firestore erişimi kullanılamıyor, JSON fallback kullanılıyor: {exc}"))
            payload = self._load_from_json(options["from_json"])

        if options["wipe"]:
            self.stdout.write("Mevcut veriler temizleniyor...")
            Favori.objects.all().delete()
            Yorum.objects.all().delete()
            MekanFoto.objects.all().delete()
            Mekan.objects.all().delete()
            Kategori.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        user_count = self._sync_users(payload["users"], from_json=used_json_fallback)
        kategori_count = self._sync_kategoriler(payload["kategoriler"], from_json=used_json_fallback)
        mekan_count = self._sync_mekanlar(payload["mekanlar"], from_json=used_json_fallback)
        foto_count = self._sync_mekan_fotograflari(payload["mekan_fotograflari"], from_json=used_json_fallback)
        yorum_count = self._sync_yorumlar(payload["yorumlar"], from_json=used_json_fallback)
        favori_count = self._sync_favoriler(payload["favoriler"], from_json=used_json_fallback)

        self.stdout.write(self.style.SUCCESS(f"Kullanıcılar: {user_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS(f"Kategoriler: {kategori_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS(f"Mekanlar: {mekan_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS(f"Mekan fotoğrafları: {foto_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS(f"Yorumlar: {yorum_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS(f"Favoriler: {favori_count} kayıt senkronlandı."))
        self.stdout.write(self.style.SUCCESS("Firebase -> SQLite aktarımı tamamlandı."))

    def _load_from_json(self, path):
        fixture_path = Path(path)
        if not fixture_path.is_absolute():
            fixture_path = settings.BASE_DIR / fixture_path
        if not fixture_path.exists():
            raise FileNotFoundError(f"JSON dosyası bulunamadı: {fixture_path}")

        data = _load_json_with_utf8_fallbacks(fixture_path)

        if not isinstance(data, list):
            raise ValueError("JSON fallback liste formatında olmalı (Django fixture).")

        return {
            "users": [item for item in data if item.get("model") == "auth.user"],
            "kategoriler": [item for item in data if item.get("model") == "gurmerota.kategori"],
            "mekanlar": [item for item in data if item.get("model") == "gurmerota.mekan"],
            "mekan_fotograflari": [item for item in data if item.get("model") == "gurmerota.mekanfoto"],
            "yorumlar": [item for item in data if item.get("model") == "gurmerota.yorum"],
            "favoriler": [item for item in data if item.get("model") == "gurmerota.favori"],
        }

    def _sync_users(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                user_pk = int(doc.get("pk"))
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                user_pk = int(data.get("id") or doc_id)

            username = data.get("username") or f"user_{user_pk}"
            defaults = {
                "username": username,
                "email": data.get("email", ""),
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "is_staff": bool(data.get("is_staff", False)),
                "is_superuser": bool(data.get("is_superuser", False)),
                "is_active": bool(data.get("is_active", True)),
            }
            user, _ = User.objects.update_or_create(pk=user_pk, defaults=defaults)
            if from_json and data.get("password"):
                user.password = data["password"]
                user.save(update_fields=["password"])
            synced += 1
        return synced

    def _sync_kategoriler(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                kategori_pk = int(doc.get("pk"))
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                kategori_pk = int(data.get("id") or doc_id)
            defaults = {
                "isim": repair_turkish_text(data.get("isim", f"Kategori {kategori_pk}")),
                "ikon_slug": data.get("ikon_slug", ""),
            }
            Kategori.objects.update_or_create(pk=kategori_pk, defaults=defaults)
            synced += 1
        return synced

    def _sync_mekanlar(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                mekan_pk = int(doc.get("pk"))
                kategori_id = data.get("kategori")
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                mekan_pk = int(data.get("id") or doc_id)
                kategori_id = data.get("kategori_id")
            if not kategori_id:
                continue

            try:
                kategori = Kategori.objects.get(pk=int(kategori_id))
            except Kategori.DoesNotExist:
                kategori = Kategori.objects.create(
                    pk=int(kategori_id),
                    isim=repair_turkish_text(data.get("kategori_adi") or f"Kategori {kategori_id}"),
                    ikon_slug="",
                )

            kapak = data.get("kapak_fotografi") or {}
            kapak_name = kapak.get("name", "") if isinstance(kapak, dict) else ""
            defaults = {
                "isim": repair_turkish_text(data.get("isim", f"Mekan {mekan_pk}")),
                "aciklama": repair_turkish_text(data.get("aciklama", "")),
                "kategori": kategori,
                "adres": repair_turkish_text(data.get("adres", "")),
                "latitude": _as_decimal(data.get("latitude"), "0"),
                "longitude": _as_decimal(data.get("longitude"), "0"),
                "telefon": data.get("telefon", ""),
                "web_sitesi": data.get("web_sitesi", ""),
                "calisma_baslangic": _as_time(data.get("calisma_baslangic")),
                "calisma_bitis": _as_time(data.get("calisma_bitis")),
                "calisma_gunleri": data.get("calisma_gunleri") or "0,1,2,3,4,5,6",
                "kapak_fotografi": kapak_name,
            }
            Mekan.objects.update_or_create(pk=mekan_pk, defaults=defaults)
            synced += 1
        return synced

    def _sync_mekan_fotograflari(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                foto_pk = int(doc.get("pk"))
                mekan_id = data.get("mekan")
                image_name = data.get("image", "")
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                foto_pk = int(data.get("id") or doc_id)
                mekan_id = data.get("mekan_id")
                image_data = data.get("image") or {}
                image_name = image_data.get("name", "") if isinstance(image_data, dict) else ""

            if not mekan_id or not Mekan.objects.filter(pk=int(mekan_id)).exists():
                continue

            defaults = {
                "mekan_id": int(mekan_id),
                "image": image_name,
                "sira": int(data.get("sira") or 0),
            }
            MekanFoto.objects.update_or_create(pk=foto_pk, defaults=defaults)
            synced += 1
        return synced

    def _sync_yorumlar(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                yorum_pk = int(doc.get("pk"))
                mekan_id = data.get("mekan")
                kullanici_id = data.get("kullanici")
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                yorum_pk = int(data.get("id") or doc_id)
                mekan_id = data.get("mekan_id")
                kullanici_id = data.get("kullanici_id")

            if not mekan_id or not kullanici_id:
                continue
            if not Mekan.objects.filter(pk=int(mekan_id)).exists():
                continue
            if not User.objects.filter(pk=int(kullanici_id)).exists():
                continue

            defaults = {
                "mekan_id": int(mekan_id),
                "kullanici_id": int(kullanici_id),
                "yorum": data.get("yorum", ""),
                "puan": int(data.get("puan") or 1),
            }
            Yorum.objects.update_or_create(pk=yorum_pk, defaults=defaults)
            synced += 1
        return synced

    def _sync_favoriler(self, docs, from_json=False):
        synced = 0
        for doc in docs:
            if from_json:
                data = doc.get("fields") or {}
                favori_pk = int(doc.get("pk"))
                mekan_id = data.get("mekan")
                kullanici_id = data.get("kullanici")
            else:
                data = doc.to_dict() or {}
                doc_id = doc.id
                favori_pk = int(data.get("id") or doc_id)
                mekan_id = data.get("mekan_id")
                kullanici_id = data.get("kullanici_id")

            if not mekan_id or not kullanici_id:
                continue
            if not Mekan.objects.filter(pk=int(mekan_id)).exists():
                continue
            if not User.objects.filter(pk=int(kullanici_id)).exists():
                continue

            defaults = {
                "mekan_id": int(mekan_id),
                "kullanici_id": int(kullanici_id),
            }
            Favori.objects.update_or_create(pk=favori_pk, defaults=defaults)
            synced += 1
        return synced
