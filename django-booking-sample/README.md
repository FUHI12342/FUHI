# 予約・開店業務管理システム

Django製の予約サイト([django-booking-sample](https://github.com/naritotakizawa/django-booking-sample) ベース)を、
リアル店舗の開店業務自動化システムへ拡張したもの。
要件定義・実装計画は [docs/store-opening-automation-requirements.md](../docs/store-opening-automation-requirements.md) を参照。

## 動かし方

```
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata initial   # サンプルデータ(店舗・スタッフ・ユーザー)
python manage.py runserver
```

その後、ブラウザで http://127.0.0.1:8000 へアクセスしてください。

### 環境変数(本番)

| 変数 | 内容 |
|---|---|
| `DJANGO_SECRET_KEY` | 必須。シークレットキー |
| `DJANGO_DEBUG` | `false` を設定(デフォルトは開発用の `true`) |
| `DJANGO_ALLOWED_HOSTS` | カンマ区切りのホスト名 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | カンマ区切りのオリジン(リバースプロキシ配下用) |

## テストする

```
coverage run --source='.' manage.py test
coverage report -m
```
