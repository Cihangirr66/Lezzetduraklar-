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

    class Meta:
        model = Mekan
        fields = "__all__"


class YorumSerializer(serializers.ModelSerializer):
    kullanici_adi = serializers.CharField(source="kullanici.username", read_only=True)

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
