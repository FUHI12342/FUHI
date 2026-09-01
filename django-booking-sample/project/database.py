"""DATABASE_URL の解釈(Cloud SQL / PostgreSQL 対応)。

依存を増やさないための最小実装。対応形式:
  postgres://USER:PASSWORD@HOST:PORT/NAME
  postgresql://USER:PASSWORD@HOST:PORT/NAME
  postgres://USER:PASSWORD@/NAME?host=/cloudsql/PROJECT:REGION:INSTANCE  (Unixソケット)
"""
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


def database_config_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('postgres', 'postgresql'):
        raise ImproperlyConfigured(
            f'DATABASE_URL のスキーム {parsed.scheme!r} は未対応です(postgres:// のみ)。'
        )
    query = parse_qs(parsed.query)
    host = parsed.hostname or ''
    if not host and 'host' in query:
        host = query['host'][0]  # Cloud SQL の Unix ソケットパス
    config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parsed.path.lstrip('/')),
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': host,
        'PORT': str(parsed.port) if parsed.port else '',
        'CONN_MAX_AGE': 60,
    }
    if not config['NAME']:
        raise ImproperlyConfigured('DATABASE_URL にデータベース名がありません。')
    return config
