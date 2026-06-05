# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from gurmerota.firebase_sync import (
    create_or_update_firebase_user,
    sync_instance,
)
from gurmerota.models import Favori, Kategori, Mekan, MekanFoto, Yorum


class Command(BaseCommand):
    help = 'SQLite/Django verilerini Firebase Firestore ve Firebase Auth tarafına aktarır.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-auth',
            action='store_true',
            help='Kullanıcıları Firebase Auth tarafına aktarma.',
        )
        parser.add_argument(
            '--ignore-errors',
            action='store_true',
            help='Firestore/Auth hatasında devam et.',
        )

    def handle(self, *args, **options):
        models = (
            ('kategoriler', Kategori.objects.all()),
            ('mekanlar', Mekan.objects.select_related('kategori').all()),
            ('mekan_fotograflari', MekanFoto.objects.select_related('mekan').all()),
            ('yorumlar', Yorum.objects.select_related('mekan', 'kullanici').all()),
            ('favoriler', Favori.objects.select_related('mekan', 'kullanici').all()),
            ('users', User.objects.all()),
        )

        if not options['skip_auth'] and settings.FIREBASE_AUTH_ENABLED:
            self.stdout.write('Firebase Auth kullanıcıları aktarılıyor...')
            for user in User.objects.all():
                self._run(
                    lambda user=user: create_or_update_firebase_user(user),
                    options['ignore_errors'],
                    f'user:{user.pk}',
                )
        elif not options['skip_auth']:
            self.stdout.write('Firebase Auth kapalı: `FIREBASE_AUTH_ENABLED=True` yapınca aktarılır.')

        for label, queryset in models:
            total = queryset.count()
            self.stdout.write(f'{label}: {total} kayıt aktarılıyor...')
            synced = 0
            for instance in queryset.iterator():
                self._run(
                    lambda instance=instance: sync_instance(instance),
                    options['ignore_errors'],
                    f'{label}:{instance.pk}',
                )
                synced += 1
            self.stdout.write(self.style.SUCCESS(f'{label}: {synced}/{total} tamam'))

        self.stdout.write(self.style.SUCCESS('Firebase aktarımı tamamlandı.'))

    def _run(self, func, ignore_errors, label):
        try:
            func()
        except Exception as exc:
            if not ignore_errors:
                raise
            self.stderr.write(self.style.WARNING(f'{label} atlandı: {exc}'))
