# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .firebase_sync import safe_delete_instance, safe_sync_instance
from .models import Favori, Kategori, Mekan, MekanFoto, Yorum


SYNCED_MODELS = (User, Kategori, Mekan, MekanFoto, Yorum, Favori)


@receiver(post_save, sender=User)
@receiver(post_save, sender=Kategori)
@receiver(post_save, sender=Mekan)
@receiver(post_save, sender=MekanFoto)
@receiver(post_save, sender=Yorum)
@receiver(post_save, sender=Favori)
def sync_saved_instance(sender, instance, **kwargs):
    safe_sync_instance(instance)
    if isinstance(instance, (Yorum, Favori, MekanFoto)):
        try:
            safe_sync_instance(instance.mekan)
        except Exception:
            pass


@receiver(post_delete, sender=User)
@receiver(post_delete, sender=Kategori)
@receiver(post_delete, sender=Mekan)
@receiver(post_delete, sender=MekanFoto)
@receiver(post_delete, sender=Yorum)
@receiver(post_delete, sender=Favori)
def sync_deleted_instance(sender, instance, **kwargs):
    safe_delete_instance(instance)
    if isinstance(instance, (Yorum, Favori, MekanFoto)) and getattr(instance, 'mekan_id', None):
        try:
            safe_sync_instance(instance.mekan)
        except Exception:
            pass
