# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache

from lezzetduraklari.firebase import (
    FirebaseIdentityError,
    FirebaseTransportError,
    verify_email_password,
)


FIREBASE_AUTH_RETRY_BLOCK_KEY = "firebase_auth_retry_blocked"
FIREBASE_AUTH_RETRY_BLOCK_SECONDS = 120


def find_user_for_login(identifier):
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    try:
        return User.objects.get(username__iexact=identifier)
    except User.DoesNotExist:
        try:
            return User.objects.get(email__iexact=identifier)
        except User.DoesNotExist:
            return None


def authenticate_with_firebase_fallback(identifier, password):
    identifier = (identifier or "").strip()
    password = password or ""
    user = authenticate(username=identifier, password=password)
    if user:
        return user

    if not getattr(settings, "FIREBASE_AUTH_ENABLED", False):
        return None
    if not getattr(settings, "FIREBASE_WEB_API_KEY", ""):
        return None
    if cache.get(FIREBASE_AUTH_RETRY_BLOCK_KEY):
        return None

    matched_user = find_user_for_login(identifier)
    if not matched_user or not matched_user.email:
        return None

    try:
        verify_email_password(matched_user.email, password)
    except FirebaseTransportError:
        cache.set(
            FIREBASE_AUTH_RETRY_BLOCK_KEY,
            True,
            timeout=FIREBASE_AUTH_RETRY_BLOCK_SECONDS,
        )
        return None
    except FirebaseIdentityError:
        return None

    matched_user.set_password(password)
    matched_user.save(update_fields=["password"])
    return matched_user
