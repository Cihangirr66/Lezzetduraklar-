from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gurmerota", "0011_turkce_model_etiketleri"),
    ]

    operations = [
        migrations.AddField(
            model_name="mekan",
            name="calisma_baslangic",
            field=models.TimeField(blank=True, null=True, verbose_name="acilis saati"),
        ),
        migrations.AddField(
            model_name="mekan",
            name="calisma_bitis",
            field=models.TimeField(blank=True, null=True, verbose_name="kapanis saati"),
        ),
        migrations.AddField(
            model_name="mekan",
            name="calisma_gunleri",
            field=models.CharField(
                blank=True,
                default="0,1,2,3,4,5,6",
                help_text="0=Pazartesi, 6=Pazar. Virgulle ayirin.",
                max_length=20,
                verbose_name="calisma gunleri",
            ),
        ),
    ]
