# -*- coding: utf-8 -*-
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("gurmerota", "0009_turkce_kategori_adlari"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="mekanfoto",
            options={
                "ordering": ("sira", "-olusturulma_tarihi"),
                "verbose_name": "Mekan Fotoğrafı",
                "verbose_name_plural": "Mekan Fotoğrafları",
            },
        ),
    ]
