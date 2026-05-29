from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Favori, Kategori, Mekan, MekanFoto, Yorum

admin.site.site_header = "Lezzet Durakları Yönetim Paneli"
admin.site.site_title = "Lezzet Durakları Yönetim"
admin.site.index_title = "İçerik, kullanıcı ve rapor yönetimi"

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "is_superuser", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    actions = ("delete_selected",)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


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
    title = "Calisma saati"
    parameter_name = "calisma_saati"

    def lookups(self, request, model_admin):
        return (
            ("var", "Calisma saati var"),
            ("yok", "Calisma saati yok"),
            ("acik", "Su an acik"),
        )

    def queryset(self, request, queryset):
        if self.value() == "var":
            return queryset.exclude(calisma_baslangic__isnull=True).exclude(calisma_bitis__isnull=True)
        if self.value() == "yok":
            return queryset.filter(Q(calisma_baslangic__isnull=True) | Q(calisma_bitis__isnull=True))
        if self.value() == "acik":
            return queryset.filter(pk__in=[mekan.pk for mekan in queryset if mekan.bugun_acik_mi()])
        return queryset


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ("isim", "ikon_slug", "mekan_sayisi")
    search_fields = ("isim", "ikon_slug")
    ordering = ("isim",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_mekan_sayisi=Count("mekanlar", distinct=True))

    def mekan_sayisi(self, obj):
        return obj._mekan_sayisi

    mekan_sayisi.short_description = "Mekan"
    mekan_sayisi.admin_order_field = "_mekan_sayisi"


@admin.register(Mekan)
class MekanAdmin(admin.ModelAdmin):
    list_display = (
        "kapak_onizleme",
        "isim",
        "kategori",
        "puan_ozeti",
        "yorum_adedi",
        "favori_adedi",
        "telefon_durumu",
        "calisma_durumu",
        "harita_butonu",
        "olusturulma_tarihi",
    )
    list_filter = ("kategori", TelefonDurumuFilter, FotografDurumuFilter, CalismaSaatiDurumuFilter, "olusturulma_tarihi")
    search_fields = ("isim", "adres", "telefon", "kategori__isim")
    readonly_fields = ("kapak_onizleme_buyuk", "harita_linki", "olusturulma_tarihi")
    autocomplete_fields = ("kategori",)
    date_hierarchy = "olusturulma_tarihi"
    list_per_page = 25
    save_on_top = True
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
            "Calisma Saatleri",
            {
                "fields": (
                    "calisma_baslangic",
                    "calisma_bitis",
                    "calisma_gunleri",
                ),
                "description": "Gunler 0=Pazartesi, 6=Pazar olacak sekilde virgulle tutulur.",
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
        return obj._yorum_adedi

    yorum_adedi.short_description = "Yorum"
    yorum_adedi.admin_order_field = "_yorum_adedi"

    def favori_adedi(self, obj):
        return obj._favori_adedi

    favori_adedi.short_description = "Favori"
    favori_adedi.admin_order_field = "_favori_adedi"

    def telefon_durumu(self, obj):
        if obj.telefon:
            return mark_safe('<span class="admin-pill success">Var</span>')
        return mark_safe('<span class="admin-pill muted">Yok</span>')

    telefon_durumu.short_description = "Telefon"

    def calisma_durumu(self, obj):
        if not obj.calisma_saati_var:
            return mark_safe('<span class="admin-pill muted">Saat yok</span>')
        if obj.bugun_acik_mi():
            return format_html('<span class="admin-pill success">Acik {}</span>', obj.calisma_ozeti)
        return format_html('<span class="admin-pill muted">Kapali {}</span>', obj.calisma_ozeti)

    calisma_durumu.short_description = "Calisma"

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
    extra = 1

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
    list_per_page = 30

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
    list_per_page = 30


@admin.register(MekanFoto)
class MekanFotoAdmin(admin.ModelAdmin):
    list_display = ("foto_onizleme", "mekan", "sira", "olusturulma_tarihi")
    list_filter = ("olusturulma_tarihi", "mekan")
    search_fields = ("mekan__isim",)
    autocomplete_fields = ("mekan",)
    readonly_fields = ("foto_onizleme_buyuk", "olusturulma_tarihi")
    list_per_page = 30

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


