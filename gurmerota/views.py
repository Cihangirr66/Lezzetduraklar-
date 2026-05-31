from datetime import datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
import random
from smtplib import SMTPException
from urllib.parse import quote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import (
    KayitFormu,
    MekanFormu,
    SifreSifirlamaFormu,
    YorumFormu,
)
from .models import Favori, Kategori, Mekan, Yorum
from .serializers import (
    FavoriSerializer,
    KategoriSerializer,
    KayitSerializer,
    KullaniciSerializer,
    MekanSerializer,
    YorumSerializer,
)


def kullanici_panel_yetkili(user):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or user.username == "cihangir"
    )


class SifreSifirlamaView(PasswordResetView):
    form_class = SifreSifirlamaFormu
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"

    def form_valid(self, form):
        site_url = urlparse(settings.PUBLIC_SITE_URL)
        domain_override = site_url.netloc or self.request.get_host()
        use_https = site_url.scheme == "https" if site_url.scheme else self.request.is_secure()
        opts = {
            "use_https": use_https,
            "token_generator": self.token_generator,
            "from_email": self.from_email,
            "email_template_name": self.email_template_name,
            "subject_template_name": self.subject_template_name,
            "request": self.request,
            "html_email_template_name": self.html_email_template_name,
            "extra_email_context": self.extra_email_context,
            "domain_override": domain_override,
        }
        try:
            form.save(**opts)
            return super(PasswordResetView, self).form_valid(form)
        except (SMTPException, OSError):
            form.add_error(
                None,
                "E-posta gönderilemedi. SMTP kullanıcı adı, uygulama şifresi veya mail sağlayıcı ayarlarını kontrol edin.",
            )
            return self.form_invalid(form)


def haversine_distance_km(lat1, lng1, lat2, lng2):
    """Return distance between two points in kilometers."""
    earth_radius_km = 6371
    lat_diff = radians(lat2 - lat1)
    lng_diff = radians(lng2 - lng1)
    a_value = (
        sin(lat_diff / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(lng_diff / 2) ** 2
    )
    c_value = 2 * asin(sqrt(a_value))
    return earth_radius_km * c_value


def _choose_best_stop(candidates, used_ids, ref_lat=None, ref_lng=None, rng=None):
    rng = rng or random
    available = [m for m in candidates if m.id not in used_ids]
    if not available:
        return None

    def score(mekan):
        puan = float(mekan.ortalama_puan or 0)
        # Freshness bonus: recently added venues should appear in routes too.
        freshness_bonus = 0.0
        if mekan.olusturulma_tarihi:
            days_old = (timezone.now() - mekan.olusturulma_tarihi).days
            if days_old <= 14:
                freshness_bonus = 1.2
            elif days_old <= 45:
                freshness_bonus = 0.7
            elif days_old <= 90:
                freshness_bonus = 0.35

        if ref_lat is None or ref_lng is None:
            return (puan + freshness_bonus, -mecan_id_safe(mekan))
        uzaklik = haversine_distance_km(
            ref_lat,
            ref_lng,
            float(mekan.latitude),
            float(mekan.longitude),
        )
        return (puan + freshness_bonus, -uzaklik)

    ranked = sorted(available, key=score, reverse=True)
    # Use a wider pool so route generation does not get stuck on the same top places.
    pool_size = min(10, len(ranked))
    pool = ranked[:pool_size]
    # Keep quality high but flatten weights to increase variety.
    weights = [max(1, pool_size - (idx // 2)) for idx in range(pool_size)]
    return rng.choices(pool, weights=weights, k=1)[0]


def mecan_id_safe(mekan):
    return int(mekan.id or 0)


ROTA_TARZ_LABELS = {
    "klasik": "Klasik",
    "sokak": "Sokak",
    "hafif": "Hafif",
    "kahvalti": "Kahvalti",
    "tatli": "Tatli",
    "kahve": "Kahve",
}


ROTA_PRESETS = (
    {
        "key": "kahvalti",
        "label": "Kahvalti Rotasi",
        "icon": "bi-cup-hot-fill",
        "description": "Firindan baslayip sakin kafe duragiyla tamamlanan sabah akisi.",
        "rota_saat": "1_2",
        "rota_tarz": "kahvalti",
    },
    {
        "key": "tatli",
        "label": "Tatli Rotasi",
        "icon": "bi-cake2-fill",
        "description": "Tatlici, dondurma ve kahve odakli keyifli bir lezzet turu.",
        "rota_saat": "2_4",
        "rota_tarz": "tatli",
    },
    {
        "key": "kahve",
        "label": "Kahve Rotasi",
        "icon": "bi-cup-hot",
        "description": "Kafe agirlikli, kisa molalarla yenilenen sehir kesfi.",
        "rota_saat": "1_2",
        "rota_tarz": "kahve",
    },
)


MESHHUR_LEZZETLER = [
    {
        "isim": "Maraş Dondurması",
        "ikon": "bi-snow2",
        "aciklama": "Keçi sütü ve salep dokusuyla uzayan, şehrin dünyaya açılan tatlı imzası.",
        "sehir": "Kahramanmaraş",
    },
    {
        "isim": "Maraş Tarhanası",
        "ikon": "bi-sun-fill",
        "aciklama": "Yoğurtlu dövme buğdaydan hazırlanan; çerez, çorba ve kızartma olarak sevilen yöresel lezzet.",
        "sehir": "Kahramanmaraş",
    },
    {
        "isim": "Eli Böğründe",
        "ikon": "bi-fire",
        "aciklama": "Kuzu eti, domates, biber ve soğanın tepside buluştuğu güçlü Maraş klasiği.",
        "sehir": "Kahramanmaraş",
    },
    {
        "isim": "Sömelek Köfte",
        "ikon": "bi-egg-fried",
        "aciklama": "İnce bulgur ve baharatla hazırlanan, yoğurt ya da sosla servis edilen geleneksel köfte.",
        "sehir": "Kahramanmaraş",
    },
    {
        "isim": "Acem Pilavı",
        "ikon": "bi-basket-fill",
        "aciklama": "Et, pirinç, havuç ve baharat dengesiyle sofralarda öne çıkan doyurucu özel gün pilavı.",
        "sehir": "Kahramanmaraş",
    },
    {
        "isim": "Maraş Çöreği",
        "ikon": "bi-flower1",
        "aciklama": "Baharatlı kokusu, gevrek yapısı ve çayla uyumuyla şehir mutfağının vazgeçilmez hamur işi.",
        "sehir": "Kahramanmaraş",
    },
]


def build_tasting_route(
    all_places,
    hours,
    style_key,
    user_lat=None,
    user_lng=None,
    rng=None,
    stage_recent_ids=None,
):
    rng = rng or random
    stage_map = {
        "klasik": [
            ("Başlangıç / Ara Sıcak", ["Sokak Lezzeti", "Fırın", "Firin", "Kahvaltı", "Kahvalti"]),
            ("Ana Yemek", ["Restoran", "Kebap", "Döner", "Doner"]),
            ("Tatlı / Kahve", ["Tatlıcı", "Tatlici", "Kafe"]),
        ],
        "sokak": [
            ("Başlangıç / Atıştırmalık", ["Sokak Lezzeti", "Fırın", "Firin", "Kahvaltı", "Kahvalti"]),
            ("Ana Yemek", ["Sokak Lezzeti", "Restoran", "Döner", "Doner", "Kebap"]),
            ("Tatlı / Çay", ["Tatlıcı", "Tatlici", "Kafe"]),
        ],
        "hafif": [
            ("Başlangıç", ["Kafe", "Fırın", "Firin", "Kahvaltı", "Kahvalti"]),
            ("Ana Yemek", ["Restoran", "Kafe", "Döner", "Doner"]),
            ("Tatlı / Kahve", ["Kafe", "Tatlıcı", "Tatlici"]),
        ],
        "kahvalti": [
            ("Firindan Baslangic", ["F\u0131r\u0131n", "Firin", "Kahvalt\u0131", "Kahvalti", "Kafe"]),
            ("Kahvalti Duragi", ["Kahvalt\u0131", "Kahvalti", "Kafe", "Restoran"]),
            ("Kahve Molasi", ["Kafe", "Tatl\u0131c\u0131", "Tatlici"]),
        ],
        "tatli": [
            ("Tatli Duragi", ["Tatl\u0131c\u0131", "Tatlici", "Kafe"]),
            ("Kahve Eslesmesi", ["Kafe", "F\u0131r\u0131n", "Firin"]),
            ("Son Lezzet", ["Tatl\u0131c\u0131", "Tatlici", "Kafe"]),
        ],
        "kahve": [
            ("Ilk Kahve", ["Kafe", "F\u0131r\u0131n", "Firin"]),
            ("Sakin Mola", ["Kafe", "Kahvalt\u0131", "Kahvalti"]),
            ("Tatli Kapanis", ["Kafe", "Tatl\u0131c\u0131", "Tatlici"]),
        ],
    }
    stages = stage_map.get(style_key, stage_map["klasik"])
    min_rating = 3.0 if hours in ("2_4", "4_plus") else 0.0

    used_ids = set()
    ref_lat = user_lat
    ref_lng = user_lng
    route = []
    fresh_cutoff = timezone.now() - timedelta(days=120)
    stage_recent_ids = stage_recent_ids or {}
    for stage_name, kategori_isimleri in stages:
        blocked_ids = set(stage_recent_ids.get(stage_name, []))
        stage_used_ids = set(used_ids) | blocked_ids
        qualified_candidates = [
            m
            for m in all_places
            if m.kategori.isim in kategori_isimleri and float(m.ortalama_puan or 0) >= min_rating
        ]
        fresh_candidates = [
            m
            for m in all_places
            if m.kategori.isim in kategori_isimleri and m.olusturulma_tarihi >= fresh_cutoff
        ]
        # Keep quality-first pool, but always mix in recent additions.
        stage_candidates = qualified_candidates + [
            m for m in fresh_candidates if m.id not in {q.id for q in qualified_candidates}
        ]
        # If still empty, fully relax by category.
        if not stage_candidates:
            stage_candidates = [m for m in all_places if m.kategori.isim in kategori_isimleri]
        stop = _choose_best_stop(stage_candidates, stage_used_ids, ref_lat, ref_lng, rng=rng)
        if not stop:
            fallback_candidates = [m for m in all_places if float(m.ortalama_puan or 0) >= min_rating]
            if not fallback_candidates:
                fallback_candidates = list(all_places)
            stop = _choose_best_stop(fallback_candidates, stage_used_ids, ref_lat, ref_lng, rng=rng)
        # If strict blocking leaves no candidates, allow blocked IDs as a last resort.
        if not stop:
            stop = _choose_best_stop(stage_candidates, used_ids, ref_lat, ref_lng, rng=rng)
        if not stop:
            continue
        used_ids.add(stop.id)
        ref_lat = float(stop.latitude)
        ref_lng = float(stop.longitude)
        route.append({"asama": stage_name, "mekan": stop})
    return route


def _route_ids(route_items):
    return [item["mekan"].id for item in route_items if item.get("mekan")]


def _pick_diverse_route(candidates, previous_ids, rng=None):
    """Prefer routes that differ from the previous one while keeping quality high."""
    if not candidates:
        return []
    rng = rng or random
    prev_set = set(previous_ids or [])

    def candidate_score(route_items):
        ids = _route_ids(route_items)
        if not ids:
            return -999
        overlap = len(set(ids) & prev_set)
        avg_rating = sum(float(item["mekan"].ortalama_puan or 0) for item in route_items) / len(route_items)
        fresh_cutoff = timezone.now() - timedelta(days=120)
        fresh_count = sum(1 for item in route_items if item["mekan"].olusturulma_tarihi >= fresh_cutoff)
        # Lower overlap is better, then higher rating; tiny jitter to avoid deterministic ties.
        return (len(ids) - overlap) * 10 + (fresh_count * 3) + avg_rating + rng.random() * 0.25

    return max(candidates, key=candidate_score)


class KategoriListView(generics.ListAPIView):
    queryset = Kategori.objects.all()
    serializer_class = KategoriSerializer


class KategoriDetailView(generics.RetrieveAPIView):
    queryset = Kategori.objects.all()
    serializer_class = KategoriSerializer


class MekanListView(generics.ListAPIView):
    serializer_class = MekanSerializer
    queryset = Mekan.objects.select_related("kategori").prefetch_related("fotograflar", "yorumlar").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        kategori = (self.request.query_params.get("kategori") or "").strip()
        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")
        radius = self.request.query_params.get("radius")

        if q:
            queryset = queryset.filter(
                Q(isim__icontains=q)
                | Q(adres__icontains=q)
                | Q(aciklama__icontains=q)
                | Q(kategori__isim__icontains=q)
            )
        if kategori:
            queryset = queryset.filter(Q(kategori_id=kategori) | Q(kategori__isim__iexact=kategori))

        if not (lat and lng and radius):
            return queryset
        try:
            center_lat = float(lat)
            center_lng = float(lng)
            radius_km = float(radius)
        except ValueError as exc:
            raise ValidationError(
                {"detail": "lat, lng ve radius sayısal değer olmalıdır."}
            ) from exc

        nearby_ids = []
        for mekan in queryset:
            distance = haversine_distance_km(
                center_lat,
                center_lng,
                float(mekan.latitude),
                float(mekan.longitude),
            )
            if distance <= radius_km:
                nearby_ids.append(mekan.id)
        return queryset.filter(id__in=nearby_ids)


class MekanDetailView(generics.RetrieveAPIView):
    queryset = Mekan.objects.select_related("kategori").prefetch_related("fotograflar", "yorumlar").all()
    serializer_class = MekanSerializer


class YorumListView(generics.ListCreateAPIView):
    serializer_class = YorumSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = Yorum.objects.select_related("mekan", "kullanici").all()
        if self.request.query_params.get("mine") == "1":
            if not self.request.user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(kullanici=self.request.user)
        mekan = self.request.query_params.get("mekan") or self.request.query_params.get("mekan_id")
        if mekan:
            queryset = queryset.filter(mekan_id=mekan)
        return queryset

    def perform_create(self, serializer):
        serializer.save(kullanici=self.request.user)


class KayitApiView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = KayitSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        user = User.objects.get(pk=response.data["id"])
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": KullaniciSerializer(user).data,
            },
            status=response.status_code,
        )


class GirisApiView(APIView):
    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")
        user = authenticate(username=username, password=password)
        if not user:
            raise ValidationError({"detail": "Kullanıcı adı veya şifre hatalı."})
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": KullaniciSerializer(user).data,
            }
        )


class ProfilApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(KullaniciSerializer(request.user).data)


class FavoriListApiView(generics.ListAPIView):
    serializer_class = FavoriSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favori.objects.select_related("mekan").filter(kullanici=self.request.user)


class FavoriToggleApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mekan_id: int):
        mekan = get_object_or_404(Mekan, pk=mekan_id)
        favori, created = Favori.objects.get_or_create(kullanici=request.user, mekan=mekan)
        if not created:
            favori.delete()
        return Response({"favoride": created, "mekan_id": mekan_id})


def home(request):
    kategori_id = request.GET.get("kategori")
    arama_q = (request.GET.get("q") or "").strip()
    min_puan_raw = (request.GET.get("min_puan") or "").strip()
    sirala = (request.GET.get("sirala") or "yakina_gore").strip()
    sadece_fotolu = request.GET.get("sadece_fotolu") == "1"
    sadece_telefonlu = request.GET.get("sadece_telefonlu") == "1"
    sadece_acik = request.GET.get("sadece_acik") == "1"
    lat_raw = (request.GET.get("lat") or "").strip()
    lng_raw = (request.GET.get("lng") or "").strip()

    kullanici_lat = None
    kullanici_lng = None
    if lat_raw and lng_raw:
        try:
            kullanici_lat = float(lat_raw)
            kullanici_lng = float(lng_raw)
        except ValueError:
            kullanici_lat = None
            kullanici_lng = None

    kategoriler = Kategori.objects.all()
    mekanlar = Mekan.objects.select_related("kategori").all()
    if kategori_id:
        mekanlar = mekanlar.filter(kategori_id=kategori_id)
    if arama_q:
        mekanlar = mekanlar.filter(
            Q(isim__icontains=arama_q)
            | Q(adres__icontains=arama_q)
            | Q(aciklama__icontains=arama_q)
            | Q(telefon__icontains=arama_q)
            | Q(kategori__isim__icontains=arama_q)
        )
    if sadece_fotolu:
        mekanlar = mekanlar.filter(fotograflar__isnull=False).distinct()
    if sadece_telefonlu:
        mekanlar = mekanlar.exclude(telefon__isnull=True).exclude(telefon__exact="")

    mekan_listesi = list(mekanlar)
    simdi = timezone.localtime()
    for mekan in mekan_listesi:
        mekan.uzaklik_km = None
        mekan.simdi_acik = mekan.bugun_acik_mi(simdi)
        if kullanici_lat is not None and kullanici_lng is not None:
            mekan.uzaklik_km = haversine_distance_km(
                kullanici_lat,
                kullanici_lng,
                float(mekan.latitude),
                float(mekan.longitude),
            )
    if sadece_acik:
        mekan_listesi = [mekan for mekan in mekan_listesi if mekan.simdi_acik]

    min_puan = None
    if min_puan_raw:
        try:
            min_puan = float(min_puan_raw)
        except ValueError:
            min_puan = None
    if min_puan is not None:
        mekan_listesi = [
            mekan for mekan in mekan_listesi if float(mekan.ortalama_puan or 0) >= min_puan
        ]

    if sirala == "puan":
        mekan_listesi.sort(key=lambda m: float(m.ortalama_puan or 0), reverse=True)
    elif sirala == "isim":
        mekan_listesi.sort(key=lambda m: m.isim.lower())
    elif sirala == "yeni":
        mekan_listesi.sort(key=lambda m: m.olusturulma_tarihi, reverse=True)
    else:
        if kullanici_lat is not None and kullanici_lng is not None:
            yakinlar = [m for m in mekan_listesi if m.uzaklik_km is not None and m.uzaklik_km <= 1]
            uzaklar = [m for m in mekan_listesi if m.uzaklik_km is None or m.uzaklik_km > 1]
            yakinlar.sort(key=lambda m: m.uzaklik_km)
            uzaklar.sort(key=lambda m: m.uzaklik_km if m.uzaklik_km is not None else 99999)
            mekan_listesi = yakinlar + uzaklar
        else:
            mekan_listesi.sort(key=lambda m: float(m.ortalama_puan or 0), reverse=True)

    paginator = Paginator(mekan_listesi, 10)
    page_number = request.GET.get("page")
    mekanlar = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    pagination_query = query_params.urlencode()

    favori_sayisi = 0
    if request.user.is_authenticated:
        favori_sayisi = Favori.objects.filter(kullanici=request.user).count()
        favori_ids = set(
            Favori.objects.filter(
                kullanici=request.user,
                mekan_id__in=[mekan.id for mekan in mekan_listesi],
            ).values_list("mekan_id", flat=True)
        )
        for mekan in mekan_listesi:
            mekan.favoride = mekan.id in favori_ids
    else:
        for mekan in mekan_listesi:
            mekan.favoride = False

    return render(
        request,
        "home.html",
        {
            "mekanlar": mekanlar,
            "pagination_query": pagination_query,
            "kategoriler": kategoriler,
            "aktif_kategori_id": str(kategori_id) if kategori_id else "",
            "favori_sayisi": favori_sayisi,
            "arama_q": arama_q,
            "aktif_min_puan": min_puan_raw,
            "aktif_sirala": sirala,
            "aktif_sadece_fotolu": sadece_fotolu,
            "aktif_sadece_telefonlu": sadece_telefonlu,
            "aktif_sadece_acik": sadece_acik,
            "aktif_lat": lat_raw,
            "aktif_lng": lng_raw,
            "konum_aktif": kullanici_lat is not None and kullanici_lng is not None,
            "panel_yetkili": kullanici_panel_yetkili(request.user),
        },
    )


def meshur_lezzetler(request):
    return render(
        request,
        "meshur_lezzetler.html",
        {
            "lezzetler": MESHHUR_LEZZETLER,
            "panel_yetkili": kullanici_panel_yetkili(request.user),
        },
    )


def rotam(request):
    rota_saat = (request.GET.get("rota_saat") or "2_4").strip()
    rota_tarz = (request.GET.get("rota_tarz") or "klasik").strip()
    rota_preset = (request.GET.get("rota_preset") or "").strip()
    lat_raw = (request.GET.get("lat") or "").strip()
    lng_raw = (request.GET.get("lng") or "").strip()
    rota_iste = request.GET.get("rota_olustur") == "1"
    rota_seed_raw = (request.GET.get("seed") or "").strip()
    try:
        rota_seed = int(rota_seed_raw) if rota_seed_raw else random.randint(1, 10_000_000)
    except ValueError:
        rota_seed = random.randint(1, 10_000_000)

    kullanici_lat = None
    kullanici_lng = None
    if lat_raw and lng_raw:
        try:
            kullanici_lat = float(lat_raw)
            kullanici_lng = float(lng_raw)
        except ValueError:
            kullanici_lat = None
            kullanici_lng = None

    mekanlar = list(Mekan.objects.select_related("kategori").all())
    for mekan in mekanlar:
        mekan.uzaklik_km = None
        if kullanici_lat is not None and kullanici_lng is not None:
            mekan.uzaklik_km = haversine_distance_km(
                kullanici_lat,
                kullanici_lng,
                float(mekan.latitude),
                float(mekan.longitude),
            )

    lezzet_rotasi = []
    rota_toplam_km = 0
    rota_maps_url = ""
    rota_baslangic = ""
    rota_bitis = ""
    if rota_iste:
        session_key = f"rota_onceki_ids::{rota_saat}::{rota_tarz}"
        stage_session_key = f"rota_onceki_stage_ids::{rota_saat}::{rota_tarz}"
        previous_ids = request.session.get(session_key, [])
        previous_stage_ids = request.session.get(stage_session_key, {})

        candidate_routes = []
        for idx in range(8):
            candidate_seed = rota_seed + (idx * 7919)
            rng = random.Random(candidate_seed)
            route = build_tasting_route(
                mekanlar,
                rota_saat,
                rota_tarz,
                kullanici_lat,
                kullanici_lng,
                rng=rng,
                stage_recent_ids=previous_stage_ids,
            )
            if route:
                candidate_routes.append(route)

        chooser_rng = random.Random(rota_seed * 13 + 7)
        lezzet_rotasi = _pick_diverse_route(candidate_routes, previous_ids, rng=chooser_rng)
        request.session[session_key] = _route_ids(lezzet_rotasi)
        new_stage_ids = {}
        for item in lezzet_rotasi:
            stage_name = item.get("asama")
            mekan = item.get("mekan")
            if not stage_name or not mekan:
                continue
            old = list(previous_stage_ids.get(stage_name, []))
            merged = [mekan.id] + [x for x in old if x != mekan.id]
            new_stage_ids[stage_name] = merged[:6]
        request.session[stage_session_key] = new_stage_ids
        request.session.modified = True

    if lezzet_rotasi:
        koordinatlar = []
        if kullanici_lat is not None and kullanici_lng is not None:
            koordinatlar.append((kullanici_lat, kullanici_lng))
            rota_baslangic = f"{kullanici_lat:.6f},{kullanici_lng:.6f}"
        for item in lezzet_rotasi:
            mekan = item["mekan"]
            koordinatlar.append((float(mekan.latitude), float(mekan.longitude)))

        for onceki, sonraki in zip(koordinatlar, koordinatlar[1:]):
            rota_toplam_km += haversine_distance_km(
                onceki[0], onceki[1], sonraki[0], sonraki[1]
            )

        durak_koordinatlari = [
            f"{item['mekan'].latitude},{item['mekan'].longitude}" for item in lezzet_rotasi
        ]
        rota_bitis = durak_koordinatlari[-1]
        if rota_baslangic:
            waypoint_parts = durak_koordinatlari[:-1]
            rota_maps_url = (
                "https://www.google.com/maps/dir/?api=1"
                f"&origin={quote(rota_baslangic)}"
                f"&destination={quote(rota_bitis)}"
            )
            if waypoint_parts:
                rota_maps_url += f"&waypoints={quote('|'.join(waypoint_parts))}"
            rota_maps_url += "&travelmode=walking"
        else:
            rota_maps_url = lezzet_rotasi[0]["mekan"].google_maps_url

    return render(
        request,
        "rotam.html",
        {
            "rota_saat": rota_saat,
            "rota_tarz": rota_tarz,
            "rota_tarz_label": ROTA_TARZ_LABELS.get(rota_tarz, "Klasik"),
            "rota_presets": ROTA_PRESETS,
            "rota_preset": rota_preset,
            "rota_iste": rota_iste,
            "lezzet_rotasi": lezzet_rotasi,
            "aktif_lat": lat_raw,
            "aktif_lng": lng_raw,
            "rota_seed": rota_seed,
            "rota_toplam_km": rota_toplam_km,
            "rota_maps_url": rota_maps_url,
            "rota_baslangic": rota_baslangic,
            "rota_bitis": rota_bitis,
        },
    )


def kayit_ol(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = KayitFormu(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Hesabınız oluşturuldu ve giriş yapıldı.")
        return redirect("home")
    return render(request, "registration/kayit.html", {"form": form})


@login_required
def profil(request):
    favoriler = (
        Favori.objects.select_related("mekan", "mekan__kategori")
        .filter(kullanici=request.user)
        .order_by("-olusturulma_tarihi")
    )
    yorumlar = (
        Yorum.objects.select_related("mekan", "mekan__kategori")
        .filter(kullanici=request.user)
        .order_by("-olusturulma_tarihi")
    )
    yorum_ozeti = yorumlar.aggregate(ortalama=Avg("puan"), toplam=Count("id"))
    son_favoriler = favoriler[:4]
    son_yorumlar = yorumlar[:5]
    onerilen_mekanlar = (
        Mekan.objects.select_related("kategori")
        .annotate(yorum_adedi=Count("yorumlar"), ortalama=Avg("yorumlar__puan"))
        .exclude(favoriler__kullanici=request.user)
        .order_by("-ortalama", "-yorum_adedi", "-olusturulma_tarihi")[:4]
    )

    return render(
        request,
        "profile.html",
        {
            "favori_sayisi": favoriler.count(),
            "yorum_sayisi": yorum_ozeti["toplam"] or 0,
            "ortalama_puan": yorum_ozeti["ortalama"] or 0,
            "son_favoriler": son_favoriler,
            "son_yorumlar": son_yorumlar,
            "onerilen_mekanlar": onerilen_mekanlar,
            "panel_yetkili": kullanici_panel_yetkili(request.user),
        },
    )


@login_required
def raporlar(request):
    if not kullanici_panel_yetkili(request.user):
        messages.error(request, "Bu sayfaya sadece yetkili panel kullanıcıları erişebilir.")
        return redirect("home")

    baslangic_raw = (request.GET.get("baslangic") or "").strip()
    bitis_raw = (request.GET.get("bitis") or "").strip()

    mekan_qs = Mekan.objects.select_related("kategori").all().order_by("-olusturulma_tarihi")
    yorum_qs = Yorum.objects.select_related("mekan", "kullanici").all().order_by("-olusturulma_tarihi")
    favori_qs = Favori.objects.select_related("mekan", "kullanici").all().order_by("-olusturulma_tarihi")

    baslangic_dt = None
    bitis_dt = None
    if baslangic_raw:
        try:
            baslangic_date = datetime.strptime(baslangic_raw, "%Y-%m-%d").date()
            baslangic_dt = timezone.make_aware(datetime.combine(baslangic_date, time.min))
        except ValueError:
            baslangic_dt = None
    if bitis_raw:
        try:
            bitis_date = datetime.strptime(bitis_raw, "%Y-%m-%d").date()
            bitis_dt = timezone.make_aware(datetime.combine(bitis_date, time.max))
        except ValueError:
            bitis_dt = None

    if baslangic_dt:
        mekan_qs = mekan_qs.filter(olusturulma_tarihi__gte=baslangic_dt)
        yorum_qs = yorum_qs.filter(olusturulma_tarihi__gte=baslangic_dt)
        favori_qs = favori_qs.filter(olusturulma_tarihi__gte=baslangic_dt)
    if bitis_dt:
        mekan_qs = mekan_qs.filter(olusturulma_tarihi__lte=bitis_dt)
        yorum_qs = yorum_qs.filter(olusturulma_tarihi__lte=bitis_dt)
        favori_qs = favori_qs.filter(olusturulma_tarihi__lte=bitis_dt)

    mekan_sayisi = mekan_qs.count()
    yorum_sayisi = yorum_qs.count()
    favori_sayisi = favori_qs.count()
    chart_max = max(mekan_sayisi, yorum_sayisi, favori_sayisi, 1)
    kategori_istatistikleri = [
        {"isim": row["kategori__isim"], "mekan_adedi": row["mekan_adedi"]}
        for row in mekan_qs.values("kategori__isim")
        .annotate(mekan_adedi=Count("id"))
        .order_by("-mekan_adedi", "kategori__isim")[:8]
    ]
    kategori_chart_max = max(
        [kategori["mekan_adedi"] for kategori in kategori_istatistikleri] or [1]
    )
    gunluk_kayitlar = (
        mekan_qs.annotate(gun=TruncDate("olusturulma_tarihi"))
        .values("gun")
        .annotate(toplam=Count("id"))
        .order_by("-gun")[:7]
    )
    gunluk_chart_max = max([kayit["toplam"] for kayit in gunluk_kayitlar] or [1])
    populer_mekanlar = (
        Mekan.objects.select_related("kategori")
        .annotate(yorum_adedi=Count("yorumlar"), ortalama=Avg("yorumlar__puan"))
        .order_by("-yorum_adedi", "-ortalama", "isim")[:8]
    )
    tum_mekanlar = Mekan.objects.select_related("kategori").annotate(
        foto_adedi=Count("fotograflar", distinct=True),
        yorum_adedi=Count("yorumlar", distinct=True),
    )
    kalite_telefon_yok = tum_mekanlar.filter(telefon="")
    kalite_fotograf_yok = tum_mekanlar.filter(kapak_fotografi="", foto_adedi=0)
    kalite_aciklama_yok = tum_mekanlar.filter(aciklama="")
    kalite_saat_yok = tum_mekanlar.filter(
        Q(calisma_baslangic__isnull=True) | Q(calisma_bitis__isnull=True)
    )
    kalite_web_yok = tum_mekanlar.filter(web_sitesi="")
    kalite_paneller = [
        {
            "label": "Telefon Yok",
            "count": kalite_telefon_yok.count(),
            "icon": "bi-telephone-x",
            "items": kalite_telefon_yok.order_by("isim")[:6],
        },
        {
            "label": "Foto Yok",
            "count": kalite_fotograf_yok.count(),
            "icon": "bi-image",
            "items": kalite_fotograf_yok.order_by("isim")[:6],
        },
        {
            "label": "Aciklama Yok",
            "count": kalite_aciklama_yok.count(),
            "icon": "bi-card-text",
            "items": kalite_aciklama_yok.order_by("isim")[:6],
        },
        {
            "label": "Saat Yok",
            "count": kalite_saat_yok.count(),
            "icon": "bi-clock-history",
            "items": kalite_saat_yok.order_by("isim")[:6],
        },
        {
            "label": "Web Yok",
            "count": kalite_web_yok.count(),
            "icon": "bi-globe2",
            "items": kalite_web_yok.order_by("isim")[:6],
        },
    ]
    kalite_toplam_sorun = sum(panel["count"] for panel in kalite_paneller)
    def kalite_skoru(mekan):
        return (
            (0 if mekan.telefon else 1)
            + (0 if mekan.kapak_fotografi or mekan.foto_adedi else 1)
            + (0 if mekan.aciklama else 1)
            + (0 if mekan.calisma_saati_var else 1)
            + (0 if mekan.web_sitesi else 1)
        )

    kalite_oncelikli = sorted(
        tum_mekanlar,
        key=lambda mekan: (-kalite_skoru(mekan), mekan.isim.lower()),
    )[:8]

    context = {
        "mekanlar": mekan_qs[:200],
        "yorumlar": yorum_qs[:200],
        "favoriler": favori_qs[:200],
        "mekan_sayisi": mekan_sayisi,
        "yorum_sayisi": yorum_sayisi,
        "favori_sayisi": favori_sayisi,
        "kullanici_sayisi": User.objects.count(),
        "yetkili_sayisi": User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).distinct().count(),
        "chart_max": chart_max,
        "kategori_istatistikleri": kategori_istatistikleri,
        "kategori_chart_max": kategori_chart_max,
        "gunluk_kayitlar": gunluk_kayitlar,
        "gunluk_chart_max": gunluk_chart_max,
        "populer_mekanlar": populer_mekanlar,
        "kalite_paneller": kalite_paneller,
        "kalite_toplam_sorun": kalite_toplam_sorun,
        "kalite_oncelikli": kalite_oncelikli,
        "baslangic": baslangic_raw,
        "bitis": bitis_raw,
        "rapor_tarihi": timezone.localtime(),
    }
    return render(request, "raporlar.html", context)


@login_required
def mekan_ekle(request):
    if not kullanici_panel_yetkili(request.user):
        messages.error(request, "Bu işlemi sadece yetkili panel kullanıcıları yapabilir.")
        return redirect("home")
    form = MekanFormu(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        mekan = form.save()
        messages.success(request, "Mekan başarıyla eklendi.")
        return redirect("mekan-detay", pk=mekan.pk)
    return render(
        request,
        "mekan_ekle.html",
        {"form": form, "sayfa_basligi": "Yeni Mekan Ekle", "buton_yazisi": "Mekanı Kaydet"},
    )


@login_required
def mekan_duzenle(request, pk):
    if not kullanici_panel_yetkili(request.user):
        messages.error(request, "Bu işlemi sadece yetkili panel kullanıcıları yapabilir.")
        return redirect("home")
    mekan = get_object_or_404(Mekan, pk=pk)
    form = MekanFormu(request.POST or None, request.FILES or None, instance=mekan)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mekan bilgileri güncellendi.")
        return redirect("mekan-detay", pk=mekan.pk)
    return render(
        request,
        "mekan_ekle.html",
        {
            "form": form,
            "sayfa_basligi": f"{mekan.isim} - Mekan Düzenle",
            "buton_yazisi": "Güncelle",
            "mekan": mekan,
        },
    )


@login_required
def mekan_sil(request, pk):
    if not kullanici_panel_yetkili(request.user):
        messages.error(request, "Bu işlemi sadece yetkili panel kullanıcıları yapabilir.")
        return redirect("home")
    mekan = get_object_or_404(Mekan, pk=pk)
    if request.method == "POST":
        mekan.delete()
        messages.success(request, "Mekan silindi.")
        return redirect("home")
    return render(request, "mekan_sil.html", {"mekan": mekan})


def mekan_detay(request, pk):
    mekan = get_object_or_404(Mekan.objects.select_related("kategori"), pk=pk)
    yorumlar = mekan.yorumlar.select_related("kullanici").all()
    form = None
    fotograflar = mekan.fotograflar.all()
    favori_var = False
    if request.user.is_authenticated:
        favori_var = Favori.objects.filter(kullanici=request.user, mekan=mekan).exists()

    if request.method == "POST" and not request.user.is_authenticated:
        messages.error(request, "Yorum yapabilmek için giriş yapmanız gerekli.")
        return redirect("giris")

    if request.user.is_authenticated:
        mevcut_yorum = Yorum.objects.filter(mekan=mekan, kullanici=request.user).first()
        form = YorumFormu(request.POST or None, instance=mevcut_yorum)
        if request.method == "POST" and form.is_valid():
            yorum = form.save(commit=False)
            yorum.kullanici = request.user
            yorum.mekan = mekan
            yorum.save()
            messages.success(request, "Yorumunuz kaydedildi.")
            return redirect("mekan-detay", pk=mekan.pk)

    return render(
        request,
        "mekan_detay.html",
        {
            "mekan": mekan,
            "yorumlar": yorumlar,
            "yorum_formu": form,
            "fotograflar": fotograflar,
            "favori_var": favori_var,
            "panel_yetkili": kullanici_panel_yetkili(request.user),
        },
    )


@login_required
def favori_toggle(request, mekan_id: int):
    if request.method != "POST":
        return redirect("mekan-detay", pk=mekan_id)

    mekan = get_object_or_404(Mekan, pk=mekan_id)
    favori, created = Favori.objects.get_or_create(kullanici=request.user, mekan=mekan)
    if not created:
        favori.delete()

    redirect_to = request.META.get("HTTP_REFERER")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(redirect_to)
    return redirect("home")


@login_required
def favorilerim(request):
    favori_mekanlar = Mekan.objects.select_related("kategori").filter(
        favoriler__kullanici=request.user
    )
    return render(request, "favoriler.html", {"favori_mekanlar": favori_mekanlar})
