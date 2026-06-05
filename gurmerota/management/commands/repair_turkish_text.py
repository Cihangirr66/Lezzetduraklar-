# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from gurmerota.models import Kategori, Mekan
from gurmerota.text_utils import repair_turkish_text


class Command(BaseCommand):
    help = "Bozulmuş Türkçe karakterleri mekan ve kategori kayıtlarında düzeltir."

    @transaction.atomic
    def handle(self, *args, **options):
        settings.FIREBASE_SYNC_ENABLED = False
        mekan_fixed = 0
        kategori_fixed = 0

        mekanlar = list(Mekan.objects.values("pk", "isim", "aciklama", "adres"))
        for mekan in mekanlar:
            fixed_isim = repair_turkish_text(mekan["isim"])
            fixed_aciklama = repair_turkish_text(mekan["aciklama"])
            fixed_adres = repair_turkish_text(mekan["adres"])
            updates = {}

            if fixed_isim != mekan["isim"]:
                updates["isim"] = fixed_isim
            if fixed_aciklama != mekan["aciklama"]:
                updates["aciklama"] = fixed_aciklama
            if fixed_adres != mekan["adres"]:
                updates["adres"] = fixed_adres

            if updates:
                Mekan.objects.filter(pk=mekan["pk"]).update(**updates)
                mekan_fixed += 1

        kategoriler = list(Kategori.objects.values("pk", "isim"))
        for kategori in kategoriler:
            fixed_isim = repair_turkish_text(kategori["isim"])
            if fixed_isim != kategori["isim"]:
                Kategori.objects.filter(pk=kategori["pk"]).update(isim=fixed_isim)
                kategori_fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Türkçe karakter düzeltmesi tamamlandı. Mekan: {mekan_fixed}, kategori: {kategori_fixed}"
            )
        )
