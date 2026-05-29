from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "SMTP ayarlarını test etmek için deneme e-postası gönderir."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Deneme e-postasının gönderileceği adres")

    def handle(self, *args, **options):
        recipient = options["email"]
        if settings.EMAIL_HOST_USER.endswith("@example.com") or settings.EMAIL_HOST_PASSWORD in (
            "",
            "your-app-password",
        ):
            raise CommandError(
                ".env içindeki EMAIL_HOST_USER ve EMAIL_HOST_PASSWORD hâlâ örnek değerlerde."
            )

        try:
            sent_count = send_mail(
                subject="Lezzet Durakları SMTP testi",
                message="Bu e-posta geldiyse şifre sıfırlama mail altyapısı çalışıyor.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except SMTPException as exc:
            raise CommandError(f"SMTP hatası: {exc}") from exc
        except OSError as exc:
            raise CommandError(f"Bağlantı hatası: {exc}") from exc

        if sent_count:
            self.stdout.write(self.style.SUCCESS(f"Test e-postası gönderildi: {recipient}"))
        else:
            raise CommandError("E-posta gönderilemedi, ancak SMTP detay hatası dönmedi.")
