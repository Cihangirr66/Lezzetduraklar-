from rest_framework import serializers

from django.contrib.auth.models import User

from .models import Favori, Kategori, Mekan, Yorum
from .firebase_sync import create_or_update_firebase_user


class KategoriSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kategori
        fields = "__all__"


class MekanSerializer(serializers.ModelSerializer):
    kategori_adi = serializers.CharField(source="kategori.isim", read_only=True)
    google_maps_url = serializers.ReadOnlyField()
    ortalama_puan = serializers.ReadOnlyField()
    calisma_ozeti = serializers.ReadOnlyField()
    kapak_url = serializers.SerializerMethodField()
    fotograf_urls = serializers.SerializerMethodField()
    simdi_acik = serializers.SerializerMethodField()
    yorum_sayisi = serializers.SerializerMethodField()

    class Meta:
        model = Mekan
        fields = "__all__"

    def _absolute_url(self, path):
        if not path:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_kapak_url(self, obj):
        if not obj.kapak_fotografi:
            return ""
        return self._absolute_url(obj.kapak_fotografi.url)

    def get_fotograf_urls(self, obj):
        return [
            self._absolute_url(foto.image.url)
            for foto in obj.fotograflar.all()
            if foto.image
        ]

    def get_simdi_acik(self, obj):
        return obj.bugun_acik_mi()

    def get_yorum_sayisi(self, obj):
        return obj.yorumlar.count()


class YorumSerializer(serializers.ModelSerializer):
    kullanici_adi = serializers.CharField(source="kullanici.username", read_only=True)
    mekan_adi = serializers.CharField(source="mekan.isim", read_only=True)

    class Meta:
        model = Yorum
        fields = "__all__"
        read_only_fields = ("kullanici", "olusturulma_tarihi")


class KayitSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def create(self, validated_data):
        password = validated_data["password"]
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=password,
        )
        create_or_update_firebase_user(user, password)
        return user


class KullaniciSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class FavoriSerializer(serializers.ModelSerializer):
    mekan_adi = serializers.CharField(source="mekan.isim", read_only=True)

    class Meta:
        model = Favori
        fields = ("id", "mekan", "mekan_adi", "olusturulma_tarihi")
