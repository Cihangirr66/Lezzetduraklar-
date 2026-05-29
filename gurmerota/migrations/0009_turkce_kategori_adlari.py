from django.db import migrations


CATEGORY_RENAMES = {
    "Tatlici": "Tatlıcı",
    "Firin": "Fırın",
    "Kahvalti": "Kahvaltı",
    "Doner": "Döner",
}


def turkce_kategori_adlari(apps, schema_editor):
    Kategori = apps.get_model("gurmerota", "Kategori")
    for eski_ad, yeni_ad in CATEGORY_RENAMES.items():
        Kategori.objects.filter(isim=eski_ad).update(isim=yeni_ad)


def eski_kategori_adlari(apps, schema_editor):
    Kategori = apps.get_model("gurmerota", "Kategori")
    for eski_ad, yeni_ad in CATEGORY_RENAMES.items():
        Kategori.objects.filter(isim=yeni_ad).update(isim=eski_ad)


class Migration(migrations.Migration):
    dependencies = [
        ("gurmerota", "0008_favori"),
    ]

    operations = [
        migrations.RunPython(turkce_kategori_adlari, eski_kategori_adlari),
    ]
