import re

from django.conf import settings
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Mekan, Yorum
from .firebase_sync import create_or_update_firebase_user


class KayitFormu(UserCreationForm):
    email = forms.EmailField(required=True, label="E-posta")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Kullanıcı adı"
        self.fields["username"].help_text = "150 karakter veya daha az olmalıdır."
        self.fields["password1"].label = "Şifre"
        self.fields["password2"].label = "Şifre (tekrar)"
        self.fields["password2"].help_text = "Doğrulama için şifrenizi yeniden girin."

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("E-posta alanı zorunludur.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta adresi zaten kullanılıyor.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["username"].strip()
        if commit:
            user.save()
            create_or_update_firebase_user(user, self.cleaned_data.get("password1"))
        return user


class GirisFormu(AuthenticationForm):
    username = forms.CharField(label="Kullanıcı adı")
    password = forms.CharField(label="Şifre", widget=forms.PasswordInput)
    error_messages = {
        "invalid_login": "Kullanıcı adı veya şifre hatalı.",
        "inactive": "Bu hesap aktif değil.",
    }


class SifreSifirlamaFormu(PasswordResetForm):
    email = forms.EmailField(label="E-posta")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("E-posta alanı zorunludur.")

        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError("Bu e-posta adresiyle kayıtlı aktif hesap bulunamadı.")

        smtp_backend = settings.EMAIL_BACKEND.endswith("smtp.EmailBackend")
        placeholder_user = settings.EMAIL_HOST_USER.endswith("@example.com")
        placeholder_password = settings.EMAIL_HOST_PASSWORD in ("", "your-app-password")
        if smtp_backend and (
            not settings.EMAIL_HOST
            or not settings.EMAIL_HOST_USER
            or not settings.EMAIL_HOST_PASSWORD
            or placeholder_user
            or placeholder_password
        ):
            raise forms.ValidationError(
                "E-posta gönderimi için SMTP ayarları tamamlanmamış. .env dosyasındaki EMAIL_HOST_USER ve EMAIL_HOST_PASSWORD değerlerini gerçek bilgilerle güncelleyin."
            )

        return email


class MekanFormu(forms.ModelForm):
    calisma_gunleri = forms.MultipleChoiceField(
        required=False,
        label="Çalışma günleri",
        choices=Mekan.HAFTA_GUNLERI,
        widget=forms.CheckboxSelectMultiple,
    )

    konum_linki = forms.CharField(
        required=False,
        label="Google Maps konum linki",
        help_text="Konum linkini yapıştırın, koordinatlar otomatik alınır.",
    )

    class Meta:
        model = Mekan
        fields = (
            "isim",
            "aciklama",
            "kategori",
            "adres",
            "telefon",
            "web_sitesi",
            "calisma_baslangic",
            "calisma_bitis",
            "calisma_gunleri",
            "kapak_fotografi",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["konum_linki"].widget.attrs["placeholder"] = (
            "Örn: https://maps.google.com/?q=37.5736,36.9371"
        )
        self._parsed_lat = None
        self._parsed_lng = None
        if self.instance and self.instance.pk:
            self.fields["calisma_gunleri"].initial = list(self.instance.calisma_gunleri_set)
            self.fields["konum_linki"].initial = (
                f"https://maps.google.com/?q={self.instance.latitude},{self.instance.longitude}"
            )
            self.fields["konum_linki"].help_text = (
                "Bos birakirsaniz mevcut koordinatlar korunur."
            )
        else:
            self.fields["konum_linki"].required = True
            self.fields["calisma_gunleri"].initial = [key for key, _ in Mekan.HAFTA_GUNLERI]
        self.fields["calisma_baslangic"].widget = forms.TimeInput(
            attrs={"type": "time"}, format="%H:%M"
        )
        self.fields["calisma_bitis"].widget = forms.TimeInput(
            attrs={"type": "time"}, format="%H:%M"
        )
        self.fields["calisma_baslangic"].input_formats = ["%H:%M"]
        self.fields["calisma_bitis"].input_formats = ["%H:%M"]

    @staticmethod
    def _extract_lat_lng_from_link(link):
        patterns = [
            r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"[?&]query=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1), match.group(2)
        return None, None

    def clean(self):
        cleaned_data = super().clean()
        konum_linki = (cleaned_data.get("konum_linki") or "").strip()
        calisma_baslangic = cleaned_data.get("calisma_baslangic")
        calisma_bitis = cleaned_data.get("calisma_bitis")
        calisma_gunleri = cleaned_data.get("calisma_gunleri") or []
        if bool(calisma_baslangic) != bool(calisma_bitis):
            raise forms.ValidationError(
                "Calisma saati icin acilis ve kapanis birlikte girilmeli."
            )
        if calisma_baslangic and calisma_bitis and not calisma_gunleri:
            raise forms.ValidationError(
                "Calisma saati girildiginde en az bir calisma gunu secin."
            )
        cleaned_data["calisma_gunleri"] = ",".join(calisma_gunleri)
        parsed_lat, parsed_lng = self._extract_lat_lng_from_link(konum_linki)

        if not parsed_lat or not parsed_lng:
            if self.instance and self.instance.pk and not konum_linki:
                self._parsed_lat = self.instance.latitude
                self._parsed_lng = self.instance.longitude
                return cleaned_data
            raise forms.ValidationError(
                "Geçerli bir Google Maps konum linki girin."
            )
        self._parsed_lat = parsed_lat
        self._parsed_lng = parsed_lng

        return cleaned_data

    def save(self, commit=True):
        mekan = super().save(commit=False)
        mekan.latitude = self._parsed_lat
        mekan.longitude = self._parsed_lng
        mekan.calisma_gunleri = self.cleaned_data.get("calisma_gunleri") or ""
        if commit:
            mekan.save()
        return mekan


class YorumFormu(forms.ModelForm):
    class Meta:
        model = Yorum
        fields = ("puan", "yorum")
        widgets = {
            "yorum": forms.Textarea(attrs={"rows": 4}),
        }
