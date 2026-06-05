# -*- coding: utf-8 -*-
from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from urllib.parse import parse_qs, urlparse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode

from .forms import MekanFormu
from .models import Favori, Kategori, Mekan
from lezzetduraklari.firebase import FirebaseTransportError


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


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    FIREBASE_SYNC_ENABLED=False,
    FIREBASE_AUTH_ENABLED=True,
    FIREBASE_WEB_API_KEY="test-web-api-key",
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset-user@example.com",
            password="old-pass-123",
        )

    @patch("gurmerota.views.send_password_reset_email")
    def test_password_reset_sends_email_with_firebase(self, send_password_reset_email_mock):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        send_password_reset_email_mock.assert_called_once_with(self.user.email)

    @override_settings(FIREBASE_WEB_API_KEY="")
    @patch("gurmerota.views.generate_password_reset_link")
    def test_password_reset_falls_back_to_generated_link_when_api_key_missing(
        self,
        generate_password_reset_link_mock,
    ):
        generate_password_reset_link_mock.return_value = "https://example.com/reset-link"

        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://example.com/reset-link")
        generate_password_reset_link_mock.assert_called_once_with(self.user.email)

    @patch("gurmerota.views.send_password_reset_email")
    def test_password_reset_falls_back_to_local_link_when_firebase_request_fails(
        self,
        send_password_reset_email_mock,
    ):
        send_password_reset_email_mock.side_effect = Exception("ssl verify failed")

        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "yerel şifre sıfırlama bağlantısı")
        self.assertContains(response, "/sifre-sifirla/")

    @patch("gurmerota.views.create_or_update_firebase_user")
    def test_password_reset_confirm_updates_firebase_password(self, firebase_sync_mock):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse("password_reset_confirm", args=[uidb64, token])

        redirect_response = self.client.get(confirm_url)
        self.assertEqual(redirect_response.status_code, 302)

        response = self.client.post(
            redirect_response.headers["Location"],
            {
                "new_password1": "new-pass-456",
                "new_password2": "new-pass-456",
            },
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-pass-456"))
        firebase_sync_mock.assert_called_once_with(self.user, "new-pass-456")


@override_settings(
    FIREBASE_SYNC_ENABLED=False,
    FIREBASE_AUTH_ENABLED=True,
    FIREBASE_WEB_API_KEY="test-web-api-key",
)
class FirebaseLoginFallbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="firebase-user",
            email="firebase-user@example.com",
            password="old-pass-123",
        )

    @patch("gurmerota.auth_utils.verify_email_password")
    def test_web_login_updates_local_password_from_firebase(self, verify_email_password_mock):
        response = self.client.post(
            reverse("giris"),
            {"username": self.user.username, "password": "new-pass-789"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("home"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-pass-789"))
        verify_email_password_mock.assert_called_once_with(self.user.email, "new-pass-789")

    @patch("gurmerota.auth_utils.verify_email_password")
    def test_api_login_updates_local_password_from_firebase(self, verify_email_password_mock):
        response = self.client.post(
            reverse("api-giris"),
            {"username": self.user.username, "password": "new-pass-999"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-pass-999"))
        verify_email_password_mock.assert_called_once_with(self.user.email, "new-pass-999")

    @patch("gurmerota.auth_utils.verify_email_password")
    def test_transport_failure_temporarily_disables_firebase_fallback(self, verify_email_password_mock):
        verify_email_password_mock.side_effect = FirebaseTransportError("ssl verify failed")

        first_response = self.client.post(
            reverse("giris"),
            {"username": self.user.username, "password": "new-pass-000"},
        )
        second_response = self.client.post(
            reverse("giris"),
            {"username": self.user.username, "password": "new-pass-000"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(verify_email_password_mock.call_count, 1)
