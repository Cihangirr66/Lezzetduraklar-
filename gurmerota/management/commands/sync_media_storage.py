# -*- coding: utf-8 -*-
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from gurmerota.models import Mekan, MekanFoto


class Command(BaseCommand):
    help = "Uploads existing local media files to the active Django default storage."

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        uploaded = 0
        skipped = 0
        missing = 0

        files = []
        files.extend(
            ("Mekan", mekan.pk, mekan.kapak_fotografi.name)
            for mekan in Mekan.objects.exclude(kapak_fotografi="")
        )
        files.extend(
            ("MekanFoto", foto.pk, foto.image.name)
            for foto in MekanFoto.objects.exclude(image="")
        )

        for model_name, object_id, storage_name in files:
            local_path = media_root / storage_name
            if not local_path.exists():
                missing += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing local file for {model_name}#{object_id}: {storage_name}"
                    )
                )
                continue

            if default_storage.exists(storage_name):
                skipped += 1
                continue

            with local_path.open("rb") as handle:
                default_storage.save(storage_name, File(handle))
            uploaded += 1
            self.stdout.write(f"Uploaded {storage_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Uploaded: {uploaded}, skipped: {skipped}, missing: {missing}"
            )
        )
