# -*- coding: utf-8 -*-
from urllib.parse import urlencode

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg
from django.utils import timezone


class Kategori(models.Model):
    isim = models.CharField("isim", max_length=120, unique=True)
    ikon_slug = models.SlugField("ikon etiketi", max_length=150, blank=True)

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"
        ordering = ("isim",)

    def __str__(self):
        return self.isim


class Mekan(models.Model):
    HAFTA_GUNLERI = (
        ("0", "Pazartesi"),
        ("1", "Salı"),
        ("2", "Çarşamba"),
        ("3", "Perşembe"),
        ("4", "Cuma"),
        ("5", "Cumartesi"),
        ("6", "Pazar"),
    )

    isim = models.CharField("isim", max_length=180)
    aciklama = models.TextField("açıklama", blank=True)
    kategori = models.ForeignKey(
        Kategori,
        verbose_name="kategori",
        on_delete=models.PROTECT,
        related_name="mekanlar",
    )
    adres = models.CharField("adres", max_length=255)
    latitude = models.DecimalField("enlem", max_digits=9, decimal_places=6)
    longitude = models.DecimalField("boylam", max_digits=9, decimal_places=6)
    telefon = models.CharField("telefon", max_length=30, blank=True)
    web_sitesi = models.URLField("web sitesi", blank=True)
    calisma_baslangic = models.TimeField("açılış saati", null=True, blank=True)
    calisma_bitis = models.TimeField("kapanış saati", null=True, blank=True)
    calisma_gunleri = models.CharField(
        "çalışma günleri",
        max_length=20,
        blank=True,
        default="0,1,2,3,4,5,6",
        help_text="0=Pazartesi, 6=Pazar. Virgülle ayırın.",
    )
    kapak_fotografi = models.ImageField("kapak fotoğrafı", upload_to="mekan_kapaklari/", blank=True)
    olusturulma_tarihi = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Mekan"
        verbose_name_plural = "Mekanlar"
        ordering = ("isim",)

    def __str__(self):
        return self.isim

    @property
    def google_maps_url(self):
        query = f"{self.isim}, {self.adres}"
        return "https://www.google.com/maps/search/?" + urlencode(
            {"api": "1", "query": query}
        )

    @property
    def calisma_saati_var(self):
        return bool(self.calisma_baslangic and self.calisma_bitis)

    @property
    def calisma_gunleri_set(self):
        if not self.calisma_gunleri:
            return {key for key, _ in self.HAFTA_GUNLERI}
        return {gun.strip() for gun in self.calisma_gunleri.split(",") if gun.strip()}

    @property
    def calisma_ozeti(self):
        if not self.calisma_saati_var:
            return "Çalışma saati eklenmemiş"
        return f"{self.calisma_baslangic:%H:%M} - {self.calisma_bitis:%H:%M}"

    def bugun_acik_mi(self, now=None):
        if not self.calisma_saati_var:
            return False
        local_now = timezone.localtime(now or timezone.now())
        if str(local_now.weekday()) not in self.calisma_gunleri_set:
            return False
        current_time = local_now.time()
        opens = self.calisma_baslangic
        closes = self.calisma_bitis
        if opens <= closes:
            return opens <= current_time <= closes
        return current_time >= opens or current_time <= closes

    @property
    def ortalama_puan(self):
        return self.yorumlar.aggregate(avg_score=Avg("puan"))["avg_score"]

    @property
    def ortalama_yildiz(self):
        score = float(self.ortalama_puan or 0)
        rounded = round(score * 2) / 2
        full = int(rounded)
        half = 1 if rounded - full >= 0.5 else 0
        empty = 5 - full - half
        return "★" * full + ("½" if half else "") + "☆" * empty


class MekanFoto(models.Model):
    mekan = models.ForeignKey(
        Mekan,
        verbose_name="mekan",
        on_delete=models.CASCADE,
        related_name="fotograflar",
    )
    image = models.ImageField("fotoğraf", upload_to="mekan_fotograflari/")
    sira = models.PositiveIntegerField("sıra", default=0)
    olusturulma_tarihi = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Mekan Fotoğrafı"
        verbose_name_plural = "Mekan Fotoğrafları"
        ordering = ("sira", "-olusturulma_tarihi")

    def __str__(self):
        return f"{self.mekan.isim} - Foto"


class Yorum(models.Model):
    PUAN_SECENEKLERI = (
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
    )

    mekan = models.ForeignKey(
        Mekan,
        verbose_name="mekan",
        on_delete=models.CASCADE,
        related_name="yorumlar",
    )
    kullanici = models.ForeignKey(
        User,
        verbose_name="kullanıcı",
        on_delete=models.CASCADE,
        related_name="yorumlari",
    )
    yorum = models.TextField("yorum")
    puan = models.PositiveSmallIntegerField("puan", choices=PUAN_SECENEKLERI)
    olusturulma_tarihi = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Yorum"
        verbose_name_plural = "Yorumlar"
        ordering = ("-olusturulma_tarihi",)
        unique_together = ("mekan", "kullanici")

    def __str__(self):
        return f"{self.kullanici.username} - {self.mekan.isim} ({self.puan})"

    @property
    def yildiz_gosterimi(self):
        return "★" * self.puan + "☆" * (5 - self.puan)


class Favori(models.Model):
    kullanici = models.ForeignKey(
        User,
        verbose_name="kullanıcı",
        on_delete=models.CASCADE,
        related_name="favorileri",
    )
    mekan = models.ForeignKey(
        Mekan,
        verbose_name="mekan",
        on_delete=models.CASCADE,
        related_name="favoriler",
    )
    olusturulma_tarihi = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "Favori"
        verbose_name_plural = "Favoriler"
        ordering = ("-olusturulma_tarihi",)
        unique_together = ("kullanici", "mekan")

    def __str__(self):
        return f"{self.kullanici.username} - {self.mekan.isim}"
