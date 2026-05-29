from datetime import datetime, time
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from urllib.parse import parse_qs, urlparse

from .forms import MekanFormu
from .models import Favori, Kategori, Mekan


class MekanGoogleMapsUrlTests(TestCase):
    def test_google_maps_url_searches_by_place_name_and_address(self):
        kategori, _ = Kategori.objects.get_or_create(isim="Kafe")
        mekan = Mekan.objects.create(
            isim="Yasar Ice",
            kategori=kategori,
            adres="5008. Sokak, Akif Inan Mahallesi, Onikisubat/Kahramanmaras",
            latitude="37.587642",
            longitude="36.892870",
        )

        parsed = urlparse(mekan.google_maps_url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.google.com")
        self.assertEqual(parsed.path, "/maps/search/")
        self.assertEqual(params["api"], ["1"])
        self.assertEqual(
            params["query"],
            [
                "Yasar Ice, 5008. Sokak, Akif Inan Mahallesi, "
                "Onikisubat/Kahramanmaras"
            ],
        )


class MekanFormuTests(TestCase):
    def test_edit_form_prefills_location_link_from_existing_coordinates(self):
        kategori, _ = Kategori.objects.get_or_create(isim="Kafe")
        mekan = Mekan.objects.create(
            isim="Yasar Ice",
            kategori=kategori,
            adres="5008. Sokak, Akif Inan Mahallesi, Onikisubat/Kahramanmaras",
            latitude="37.587642",
            longitude="36.892870",
        )

        form = MekanFormu(instance=mekan)

        self.assertEqual(
            form.fields["konum_linki"].initial,
            "https://maps.google.com/?q=37.587642,36.892870",
        )

    def test_form_saves_selected_working_days_as_comma_separated_values(self):
        kategori, _ = Kategori.objects.get_or_create(isim="Kafe")
        mekan = Mekan.objects.create(
            isim="Yasar Ice",
            kategori=kategori,
            adres="5008. Sokak, Akif Inan Mahallesi, Onikisubat/Kahramanmaras",
            latitude="37.587642",
            longitude="36.892870",
            calisma_gunleri="",
        )
        form = MekanFormu(
            data={
                "isim": mekan.isim,
                "aciklama": mekan.aciklama,
                "kategori": str(kategori.id),
                "adres": mekan.adres,
                "telefon": mekan.telefon,
                "web_sitesi": mekan.web_sitesi,
                "calisma_baslangic": "07:00",
                "calisma_bitis": "21:00",
                "calisma_gunleri": ["0", "1", "2", "3", "4", "5", "6"],
                "konum_linki": "https://maps.google.com/?q=37.587642,36.892870",
            },
            instance=mekan,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        self.assertEqual(saved.calisma_gunleri, "0,1,2,3,4,5,6")

    def test_blank_working_days_fall_back_to_every_day(self):
        kategori, _ = Kategori.objects.get_or_create(isim="Kafe")
        mekan = Mekan.objects.create(
            isim="Yasar Ice",
            kategori=kategori,
            adres="5008. Sokak, Akif Inan Mahallesi, Onikisubat/Kahramanmaras",
            latitude="37.587642",
            longitude="36.892870",
            calisma_baslangic=time(7, 0),
            calisma_bitis=time(21, 0),
            calisma_gunleri="",
        )
        monday_noon = timezone.make_aware(datetime(2026, 5, 25, 12, 0))

        self.assertEqual(mekan.calisma_gunleri_set, {"0", "1", "2", "3", "4", "5", "6"})
        self.assertTrue(mekan.bugun_acik_mi(monday_noon))


class NavigationAndFavoriteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="black", password="test-pass-123")
        self.kategori, _ = Kategori.objects.get_or_create(isim="Kafe")
        self.mekan = Mekan.objects.create(
            isim="Test Mekan",
            kategori=self.kategori,
            adres="Trabzon Caddesi, Kahramanmaras",
            latitude="37.575000",
            longitude="36.922000",
        )

    def test_meshur_lezzetler_page_renders(self):
        response = self.client.get(reverse("meshur-lezzetler"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En Meşhur Lezzetler")
        self.assertContains(response, "Maraş Dondurması")

    def test_favorite_toggle_returns_to_referrer(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("favori-toggle", args=[self.mekan.id]),
            HTTP_REFERER="http://testserver/?sirala=puan",
        )

        self.assertRedirects(
            response,
            "http://testserver/?sirala=puan",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Favori.objects.filter(kullanici=self.user, mekan=self.mekan).exists()
        )
