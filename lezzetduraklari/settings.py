import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    os.getenv(
        'SECRET_KEY',
        'django-insecure-local-lezzetduraklari',
    ),
)
DEBUG = os.getenv('DJANGO_DEBUG', os.getenv('DEBUG', 'True')) == 'True'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        'DJANGO_ALLOWED_HOSTS',
        os.getenv('ALLOWED_HOSTS', '192.168.1.57,127.0.0.1,localhost,*'),
    ).split(',')
    if host.strip()
]
PUBLIC_SITE_URL = os.getenv('PUBLIC_SITE_URL', 'http://127.0.0.1:8001').rstrip('/')


INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'gurmerota.apps.GurmerotaConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lezzetduraklari.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lezzetduraklari.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'tr'
TIME_ZONE = os.getenv('TIME_ZONE', 'Europe/Istanbul')
USE_I18N = True
USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'True') == 'True'
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = ''.join(os.getenv('EMAIL_HOST_PASSWORD', '').split())
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER or 'no-reply@lezzetduraklari.local',
)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'


FIREBASE_CREDENTIALS_PATH = os.getenv(
    'FIREBASE_CREDENTIALS_PATH',
    str(BASE_DIR / 'firebase-service-account.json'),
)
FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON', '')
FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', '')
FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET', '')
FIREBASE_SYNC_ENABLED = os.getenv('FIREBASE_SYNC_ENABLED', 'True') == 'True'
FIREBASE_AUTH_ENABLED = os.getenv('FIREBASE_AUTH_ENABLED', 'False') == 'True'
FIREBASE_STORAGE_ENABLED = os.getenv('FIREBASE_STORAGE_ENABLED', 'False') == 'True'

if FIREBASE_STORAGE_ENABLED:
    STORAGES['default']['BACKEND'] = 'lezzetduraklari.storage.FirebaseStorage'


JAZZMIN_SETTINGS = {
    'site_title': 'Lezzet Durakları Yönetim',
    'site_header': 'Lezzet Durakları',
    'site_brand': 'Lezzet Durakları',
    'site_logo': 'images/lezzet-duraklari-logo.png',
    'login_logo': 'images/lezzet-duraklari-logo.png',
    'site_icon': 'images/lezzet-duraklari-logo.png',
    'site_logo_classes': 'img-circle elevation-2',
    'welcome_sign': 'Lezzet Durakları yönetim paneline hoş geldiniz',
    'copyright': 'Lezzet Durakları',
    'search_model': 'gurmerota.Mekan',
    'topmenu_links': [
        {'name': 'Siteyi Aç', 'url': 'home', 'icon': 'fas fa-compass'},
        {'name': 'Raporlar', 'url': 'raporlar', 'icon': 'fas fa-chart-line'},
        {'model': 'gurmerota.Mekan'},
        {'app': 'gurmerota'},
    ],
    'custom_links': {
        'gurmerota': [
            {
                'name': 'Yeni Mekan',
                'url': 'admin:gurmerota_mekan_add',
                'icon': 'fas fa-plus-circle',
            },
            {
                'name': 'Raporlar',
                'url': 'raporlar',
                'icon': 'fas fa-chart-pie',
            },
        ],
    },
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.User': 'fas fa-user-shield',
        'gurmerota': 'fas fa-utensils',
        'gurmerota.Kategori': 'fas fa-tags',
        'gurmerota.Mekan': 'fas fa-map-marker-alt',
        'gurmerota.MekanFoto': 'fas fa-images',
        'gurmerota.Yorum': 'fas fa-star-half-alt',
        'gurmerota.Favori': 'fas fa-heart',
        'authtoken.Token': 'fas fa-key',
    },
    'order_with_respect_to': [
        'gurmerota.Mekan',
        'gurmerota.Kategori',
        'gurmerota.MekanFoto',
        'gurmerota.Yorum',
        'gurmerota.Favori',
        'auth.User',
        'authtoken.Token',
    ],
    'custom_css': 'admin/custom_admin.css',
    'related_modal_active': True,
    'navigation_expanded': True,
    'show_ui_builder': False,
    'show_theme_chooser': True,
    'changeform_format': 'horizontal_tabs',
}

JAZZMIN_UI_TWEAKS = {
    'theme': 'darkly',
    'default_theme_mode': 'dark',
    'navbar': 'navbar-dark navbar-black',
    'sidebar': 'sidebar-dark-warning',
    'accent': 'accent-warning',
    'navbar_fixed': True,
    'sidebar_fixed': True,
    'button_classes': {
        'primary': 'btn-warning',
        'secondary': 'btn-outline-light',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}
