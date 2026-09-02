"""Django settings.

設定値は環境変数から読む。開発時は未設定でも動く(SQLite・DEBUG=true・コンソールメール)。
本番(DJANGO_DEBUG=false)では DJANGO_SECRET_KEY が必須で、無ければ起動しない。
環境変数の一覧は README とdocs/external-setup-guide.md を参照。
"""
import datetime
import os

import jpholiday
from django.core.exceptions import ImproperlyConfigured

from .database import database_config_from_url

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- 環境変数ヘルパー ---------------------------------------------------------

def env(name, default=''):
    return os.environ.get(name, default)


def env_bool(name, default):
    return env(name, 'true' if default else 'false').lower() in ('1', 'true', 'yes')


def env_int(name, default):
    return int(env(name, str(default)))


def env_list(name):
    return [item for item in env(name).split(',') if item]


# --- 基本・セキュリティ ---------------------------------------------------------

DEBUG = env_bool('DJANGO_DEBUG', True)

# 旧リポジトリにコミットされていたキーは漏洩済みとして扱い、使用しない。
_DEV_SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
SECRET_KEY = env('DJANGO_SECRET_KEY', _DEV_SECRET_KEY)
if not DEBUG and SECRET_KEY == _DEV_SECRET_KEY:
    # 本番でシークレット未設定のまま起動しない(フェイルセーフ)。
    raise ImproperlyConfigured('DJANGO_DEBUG=false のときは DJANGO_SECRET_KEY の設定が必須です。')

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS') or (['localhost', '127.0.0.1'] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

if not DEBUG:
    # 本番のHTTPS強制。Cloud Run はプロキシ終端のため X-Forwarded-Proto で判定する。
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS は控えめな初期値(1時間)。includeSubDomains / preload は解除がほぼ効かないため
    # 独自ドメイン運用が固まるまで意図的に有効化しない。
    SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 3600)


# --- アプリケーション ---------------------------------------------------------

INSTALLED_APPS = [
    'booking.apps.BookingConfig',
    'attendance.apps.AttendanceConfig',
    'operations.apps.OperationsConfig',
    'sns.apps.SnsConfig',
    'inventory.apps.InventoryConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'
WSGI_APPLICATION = 'project.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LOGIN_URL = 'booking:login'
LOGIN_REDIRECT_URL = 'booking:store_list'
LOGOUT_REDIRECT_URL = 'booking:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- データベース ---------------------------------------------------------------

# 本番は DATABASE_URL(PostgreSQL / Cloud SQL)。Cloud Run はコンテナ再作成で
# ローカルファイルが消えるため、SQLite は開発専用。
if env('DATABASE_URL'):
    DATABASES = {'default': database_config_from_url(env('DATABASE_URL'))}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }


# --- 国際化 -------------------------------------------------------------------

LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# 日本の祝日(前年〜翌年)。ハードコードだと毎年メンテが必要になるため jpholiday で生成する。
_this_year = datetime.date.today().year
PUBLIC_HOLIDAYS = [
    d for year in range(_this_year - 1, _this_year + 2) for d, _name in jpholiday.year_holidays(year)
]


# --- 静的ファイル・メディア -----------------------------------------------------

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = env('DJANGO_MEDIA_ROOT', os.path.join(BASE_DIR, 'media'))
# SNS画像の公開URL(Instagram は公開URL必須)。Cloud Storage 公開バケット等。
PUBLIC_MEDIA_BASE_URL = env('PUBLIC_MEDIA_BASE_URL')


# --- メール(発注書送信) --------------------------------------------------------

EMAIL_BACKEND = env('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('DJANGO_EMAIL_HOST')
EMAIL_PORT = env_int('DJANGO_EMAIL_PORT', 587)
EMAIL_HOST_USER = env('DJANGO_EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('DJANGO_EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env_bool('DJANGO_EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = env('DJANGO_DEFAULT_FROM_EMAIL', 'noreply@example.com')


# --- エラートラッキング(任意) ---------------------------------------------------

SENTRY_DSN = env('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env('SENTRY_ENVIRONMENT', 'development' if DEBUG else 'production'),
        send_default_pii=False,  # 予約者名・キャスト名等の個人情報は送らない
        traces_sample_rate=float(env('SENTRY_TRACES_SAMPLE_RATE', '0')),
    )
