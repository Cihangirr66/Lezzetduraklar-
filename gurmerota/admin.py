# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django import forms
from django.db.models import Avg, Count, Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Favori, Kategori, Mekan, MekanFoto, Yorum

admin.site.site_header = "Lezzet Durakları Yönetim Paneli"
admin.site.site_title = "Lezzet Durakları Yönetim"
admin.site.index_title = "İçerik, kullanıcı ve rapor yönetimi"

admin.site.unregister(User)


class MekanAdminForm(forms.ModelForm):
    calisma_gunleri = forms.MultipleChoiceField(
        choices=Mekan.HAFTA_GUNLERI,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="çalışma günleri",
        help_text="Mekanın açık olduğu günleri seçin.",
    )

    class Meta:
        model = Mekan
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        value = self.instance.calisma_gunleri if self.instance and self.instance.pk else "0,1,2,3,4,5,6"
        self.fields["calisma_gunleri"].initial = [
            gun.strip() for gun in value.split(",") if gun.strip()
        ]

    def clean_calisma_gunleri(self):
        gunler = self.cleaned_data.get("calisma_gunleri") or []
        return ",".join(gunler)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "ad_soyad",
        "yetki_ozeti",
        "is_active",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    actions = ("delete_selected",)
    list_per_page = 30
    show_facets = admin.ShowFacets.ALLOW

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def ad_soyad(self, obj):
        full_name = obj.get_full_name()
        return full_name or mark_safe('<span class="admin-empty">Yok</span>')

    ad_soyad.short_description = "Ad soyad"

    def yetki_ozeti(self, obj):
        if obj.is_superuser:
            return mark_safe('<span class="admin-pill danger">Super admin</span>')
        if obj.is_staff:
            return mark_safe('<span class="admin-pill success">Yetkili</span>')
        return mark_safe('<span class="admin-pill muted">Kullanıcı</span>')

    yetki_ozeti.short_description = "Yetki"


class TelefonDurumuFilter(admin.SimpleListFilter):
    title = "Telefon"
    parameter_name = "telefon_durumu"

    def lookups(self, request, model_admin):
        return (
            ("var", "Telefonu var"),
            ("yok", "Telefonu yok"),
        )

    def queryset(self, request, queryset):
        if self.value() == "var":
            return queryset.exclude(telefon__isnull=True).exclude(telefon__exact="")
        if self.value() == "yok":
            return queryset.filter(telefon="")
        return queryset


class FotografDurumuFilter(admin.SimpleListFilter):
    title = "Fotoğraf"
    parameter_name = "fotograf_durumu"

    def lookups(self, request, model_admin):
        return (
            ("kapak", "Kapak fotoğrafı var"),
            ("galeri", "Galeri fotoğrafı var"),
            ("yok", "Fotoğraf yok"),
        )

    def queryset(self, request, queryset):
        if self.value() == "kapak":
            return queryset.exclude(kapak_fotografi="")
        if self.value() == "galeri":
            return queryset.filter(fotograflar__isnull=False).distinct()
        if self.value() == "yok":
            return queryset.filter(kapak_fotografi="", fotograflar__isnull=True)
        return queryset


class CalismaSaatiDurumuFilter(admin.SimpleListFilter):
    title = "Çalışma saati"
    parameter_name = "calisma_saati"

    def lookups(self, request, model_admin):
        return (
            ("var", "Çalışma saati var"),
            ("yok", "Çalışma saati yok"),
            ("acik", "Şu an açık"),
        )

    def queryset(self, request, queryset):
        if self.value() == "var":
            return queryset.exclude(calisma_baslangic__isnull=True).exclude(calisma_bitis__isnull=True)
        if self.value() == "yok":
            return queryset.filter(Q(calisma_baslangic__isnull=True) | Q(calisma_bitis__isnull=True))
        if self.value() == "acik":
            return queryset.filter(pk__in=[mekan.pk for mekan in queryset if mekan.bugun_acik_mi()])
        return queryset


class IcerikKalitesiFilter(admin.SimpleListFilter):
    title = "İçerik kalitesi"
    parameter_name = "icerik_kalitesi"

    def lookups(self, request, model_admin):
        return (
            ("eksik_telefon", "Telefon eksik"),
            ("eksik_fotograf", "Fotoğraf eksik"),
            ("eksik_aciklama", "Açıklama eksik"),
            ("eksik_saat", "Çalışma saati eksik"),
            ("eksik_web", "Web sitesi eksik"),
            ("tam", "Temel bilgiler tamam"),
        )

    def queryset(self, request, queryset):
        if self.value() == "eksik_telefon":
            return queryset.filter(Q(telefon__isnull=True) | Q(telefon=""))
        if self.value() == "eksik_fotograf":
            return queryset.annotate(_foto_sayisi=Count("fotograflar", distinct=True)).filter(
                kapak_fotografi="",
                _foto_sayisi=0,
            )
        if self.value() == "eksik_aciklama":
            return queryset.filter(aciklama="")
        if self.value() == "eksik_saat":
            return queryset.filter(Q(calisma_baslangic__isnull=True) | Q(calisma_bitis__isnull=True))
        if self.value() == "eksik_web":
            return queryset.filter(web_sitesi="")
        if self.value() == "tam":
            return queryset.annotate(_foto_sayisi=Count("fotograflar", distinct=True)).exclude(
                Q(telefon__isnull=True)
                | Q(telefon="")
                | Q(aciklama="")
                | Q(calisma_baslangic__isnull=True)
                | Q(calisma_bitis__isnull=True)
                | Q(web_sitesi="")
            ).filter(Q(kapak_fotografi__gt="") | Q(_foto_sayisi__gt=0))
        return queryset


class PuanDurumuFilter(admin.SimpleListFilter):
    title = "Puan durumu"
    parameter_name = "puan_durumu"

    def lookups(self, request, model_admin):
        return (
            ("4_plus", "4.0 ve üstü"),
            ("3_4", "3.0 - 3.9"),
            ("dusuk", "3.0 altı"),
            ("yorumsuz", "Henüz yorum yok"),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(_puan_filter=Avg("yorumlar__puan"))
        if self.value() == "4_plus":
            return queryset.filter(_puan_filter__gte=4)
        if self.value() == "3_4":
            return queryset.filter(_puan_filter__gte=3, _puan_filter__lt=4)
        if self.value() == "dusuk":
            return queryset.filter(_puan_filter__lt=3)
        if self.value() == "yorumsuz":
            return queryset.filter(_puan_filter__isnull=True)
        return queryset


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ("isim", "ikon_slug", "mekan_sayisi", "ortalama_puan")
    list_editable = ("ikon_slug",)
    search_fields = ("isim", "ikon_slug")
    ordering = ("isim",)
    show_facets = admin.ShowFacets.ALLOW

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _mekan_sayisi=Count("mekanlar", distinct=True),
            _ortalama_puan=Avg("mekanlar__yorumlar__puan"),
        )

    def mekan_sayisi(self, obj):
        return obj._mekan_sayisi

    mekan_sayisi.short_description = "Mekan"
    mekan_sayisi.admin_order_field = "_mekan_sayisi"

    def ortalama_puan(self, obj):
        puan = obj._ortalama_puan
        if puan is None:
            return mark_safe('<span class="admin-empty">Yorum yok</span>')
        return format_html('<span class="admin-rating">{}</span>', f"{puan:.1f}")

    ortalama_puan.short_description = "Ortalama"
    ortalama_puan.admin_order_field = "_ortalama_puan"


@admin.action(description="Seçili mekanları her gün açık olarak işaretle")
def her_gun_acik_yap(modeladmin, request, queryset):
    updated = queryset.update(calisma_gunleri="0,1,2,3,4,5,6")
    modeladmin.message_user(request, f"{updated} mekanın çalışma günleri güncellendi.")


@admin.action(description="Seçili mekanlarda web sitesi alanını temizle")
def web_sitesi_temizle(modeladmin, request, queryset):
    updated = queryset.update(web_sitesi="")
    modeladmin.message_user(request, f"{updated} mekanın web sitesi alanı temizlendi.")


@admin.register(Mekan)
class MekanAdmin(admin.ModelAdmin):
    form = MekanAdminForm
    list_display = (
        "kapak_onizleme",
        "isim",
        "kategori",
        "puan_ozeti",
        "yorum_adedi",
        "favori_adedi",
        "foto_adedi",
        "telefon_durumu",
        "calisma_durumu",
        "web_sitesi_butonu",
        "harita_butonu",
        "olusturulma_tarihi",
    )
    list_display_links = ("kapak_onizleme", "isim")
    list_filter = (
        "kategori",
        IcerikKalitesiFilter,
        PuanDurumuFilter,
        TelefonDurumuFilter,
        FotografDurumuFilter,
        CalismaSaatiDurumuFilter,
        "olusturulma_tarihi",
    )
    search_fields = ("isim", "adres", "telefon", "kategori__isim")
    readonly_fields = ("kapak_onizleme_buyuk", "harita_linki", "olusturulma_tarihi")
    autocomplete_fields = ("kategori",)
    date_hierarchy = "olusturulma_tarihi"
    list_select_related = ("kategori",)
    list_per_page = 25
    save_on_top = True
    show_facets = admin.ShowFacets.ALLOW
    actions = (her_gun_acik_yap, web_sitesi_temizle)
    fieldsets = (
        (
            "Temel Bilgiler",
            {
                "fields": (
                    "kapak_onizleme_buyuk",
                    "isim",
                    "aciklama",
                    "kategori",
                    "adres",
                    "telefon",
                    "web_sitesi",
                    "kapak_fotografi",
                )
            },
        ),
        (
            "Çalışma Saatleri",
            {
                "fields": (
                    "calisma_baslangic",
                    "calisma_bitis",
                    "calisma_gunleri",
                ),
                "description": "Günleri checkbox ile seçebilirsiniz. Saat girilmezse mekan eksik saat olarak görünür.",
            },
        ),
        (
            "Konum",
            {
                "fields": ("latitude", "longitude", "harita_linki"),
                "description": "Koordinat girişi sonrasında haritada açmak için linki kullanın.",
            },
        ),
        ("Sistem", {"fields": ("olusturulma_tarihi",)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _yorum_adedi=Count("yorumlar", distinct=True),
            _favori_adedi=Count("favoriler", distinct=True),
            _foto_adedi=Count("fotograflar", distinct=True),
            _ortalama_puan=Avg("yorumlar__puan"),
        )

    def kapak_onizleme(self, obj):
        if obj.kapak_fotografi:
            return format_html(
                '<img src="{}" alt="{}" class="admin-thumb">',
                obj.kapak_fotografi.url,
                obj.isim,
            )
        return mark_safe('<span class="admin-empty">Yok</span>')

    kapak_onizleme.short_description = "Kapak"

    def kapak_onizleme_buyuk(self, obj):
        if obj and obj.kapak_fotografi:
            return format_html(
                '<img src="{}" alt="{}" class="admin-preview">',
                obj.kapak_fotografi.url,
                obj.isim,
            )
        return "Kapak fotoğrafı yok."

    kapak_onizleme_buyuk.short_description = "Kapak Önizleme"

    def puan_ozeti(self, obj):
        puan = obj._ortalama_puan or 0
        return format_html('<span class="admin-rating">Puan {}</span>', f"{puan:.1f}")

    puan_ozeti.short_description = "Puan"
    puan_ozeti.admin_order_field = "_ortalama_puan"

    def yorum_adedi(self, obj):
        return format_html('<span class="admin-counter">{}</span>', obj._yorum_adedi)

    yorum_adedi.short_description = "Yorum"
    yorum_adedi.admin_order_field = "_yorum_adedi"

    def favori_adedi(self, obj):
        return format_html('<span class="admin-counter">{}</span>', obj._favori_adedi)

    favori_adedi.short_description = "Favori"
    favori_adedi.admin_order_field = "_favori_adedi"

    def foto_adedi(self, obj):
        return format_html('<span class="admin-counter">{}</span>', obj._foto_adedi)

    foto_adedi.short_description = "Foto"
    foto_adedi.admin_order_field = "_foto_adedi"

    def telefon_durumu(self, obj):
        if obj.telefon:
            return mark_safe('<span class="admin-pill success">Var</span>')
        return mark_safe('<span class="admin-pill muted">Yok</span>')

    telefon_durumu.short_description = "Telefon"

    def calisma_durumu(self, obj):
        if not obj.calisma_saati_var:
            return mark_safe('<span class="admin-pill muted">Saat yok</span>')
        if obj.bugun_acik_mi():
            return format_html('<span class="admin-pill success">Açık {}</span>', obj.calisma_ozeti)
        return format_html('<span class="admin-pill muted">Kapalı {}</span>', obj.calisma_ozeti)

    calisma_durumu.short_description = "Çalışma"

    def web_sitesi_butonu(self, obj):
        if not obj.web_sitesi:
            return mark_safe('<span class="admin-empty">Yok</span>')
        return format_html(
            '<a class="admin-map-btn" href="{}" target="_blank" rel="noopener">Web</a>',
            obj.web_sitesi,
        )

    web_sitesi_butonu.short_description = "Web"

    def harita_butonu(self, obj):
        return format_html(
            '<a class="admin-map-btn" href="{}" target="_blank" rel="noopener">Harita</a>',
            obj.google_maps_url,
        )

    harita_butonu.short_description = "Konum"

    def harita_linki(self, obj):
        if obj and obj.latitude and obj.longitude:
            url = obj.google_maps_url
            return format_html('<a class="admin-map-btn" href="{}" target="_blank">Haritada Aç</a>', url)
        return "Koordinat girildiğinde görünür."

    harita_linki.short_description = "Harita Önizleme"


class MekanFotoInline(admin.TabularInline):
    model = MekanFoto
    fields = ("image", "foto_onizleme", "sira", "olusturulma_tarihi")
    readonly_fields = ("foto_onizleme", "olusturulma_tarihi")
    extra = 0
    show_change_link = True

    def foto_onizleme(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" class="admin-thumb" alt="Foto">', obj.image.url)
        return "Henüz yüklenmedi."

    foto_onizleme.short_description = "Önizleme"


MekanAdmin.inlines = [MekanFotoInline]


@admin.register(Yorum)
class YorumAdmin(admin.ModelAdmin):
    list_display = ("mekan", "kullanici", "puan_badge", "yorum_kisa", "olusturulma_tarihi")
    list_filter = ("puan", "mekan", "olusturulma_tarihi")
    search_fields = ("mekan__isim", "kullanici__username", "yorum")
    autocomplete_fields = ("mekan", "kullanici")
    date_hierarchy = "olusturulma_tarihi"
    list_select_related = ("mekan", "kullanici")
    list_per_page = 30
    show_facets = admin.ShowFacets.ALLOW

    def puan_badge(self, obj):
        return format_html('<span class="admin-rating">Puan {}/5</span>', obj.puan)

    puan_badge.short_description = "Puan"
    puan_badge.admin_order_field = "puan"

    def yorum_kisa(self, obj):
        return obj.yorum[:90] + ("..." if len(obj.yorum) > 90 else "")

    yorum_kisa.short_description = "Yorum"


@admin.register(Favori)
class FavoriAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "mekan", "olusturulma_tarihi")
    list_filter = ("olusturulma_tarihi",)
    search_fields = ("kullanici__username", "mekan__isim")
    autocomplete_fields = ("kullanici", "mekan")
    date_hierarchy = "olusturulma_tarihi"
    list_select_related = ("kullanici", "mekan")
    list_per_page = 30
    show_facets = admin.ShowFacets.ALLOW


@admin.register(MekanFoto)
class MekanFotoAdmin(admin.ModelAdmin):
    list_display = ("foto_onizleme", "mekan", "sira", "olusturulma_tarihi")
    list_filter = ("olusturulma_tarihi", "mekan")
    search_fields = ("mekan__isim",)
    autocomplete_fields = ("mekan",)
    readonly_fields = ("foto_onizleme_buyuk", "olusturulma_tarihi")
    list_select_related = ("mekan",)
    list_per_page = 30
    show_facets = admin.ShowFacets.ALLOW

    def foto_onizleme(self, obj):
        if obj.image:
            return format_html('<img src="{}" class="admin-thumb" alt="Foto">', obj.image.url)
        return mark_safe('<span class="admin-empty">Yok</span>')

    foto_onizleme.short_description = "Foto"

    def foto_onizleme_buyuk(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" class="admin-preview" alt="Foto">', obj.image.url)
        return "Fotoğraf yok."

    foto_onizleme_buyuk.short_description = "Önizleme"

