# 予約・開店業務管理システム

Django製の予約サイト([django-booking-sample](https://github.com/naritotakizawa/django-booking-sample) ベース)を、
リアル店舗の開店業務自動化システムへ拡張したもの。

## 資料

| 資料 | 内容 |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | プロジェクト案内・設計ルール・アプリ構成(最初に読む) |
| [docs/store-opening-automation-requirements.md](../docs/store-opening-automation-requirements.md) | 要件定義・見送り判断・実装済み管理表 |
| [docs/operations-model.md](../docs/operations-model.md) | 権限マトリクス・日次運用・障害時フォールバック |
| [docs/backlog.md](../docs/backlog.md) | 未着手タスク(GitHub Issues 対応) |
| [docs/CHANGELOG.md](../docs/CHANGELOG.md) | 実装履歴 |
| [docs/external-setup-guide.md](../docs/external-setup-guide.md) | 外部サービス設定手順 |

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
| `DATABASE_URL` | 本番DB。`postgres://user:pass@host:5432/name` または Cloud SQL ソケット `postgres://user:pass@/name?host=/cloudsql/PROJECT:REGION:INSTANCE`(未設定なら SQLite) |
| `SENTRY_DSN` | エラートラッキング(任意) |
| `DJANGO_HSTS_SECONDS` | HSTS 秒数(デフォルト3600) |

運用フロー・役割分担は [docs/operations-model.md](../docs/operations-model.md) を参照。

## 主な画面

| URL | 内容 |
|---|---|
| `/` | 店舗一覧・予約カレンダー(既存) |
| `/ops/store/<id>/today/` | 開店ダッシュボード(チェックリスト・開閉店・当日シフト) |
| `/attendance/` | 自分の勤怠(出退勤打刻) |
| `/store/<id>/seats/` | 座席ボード(予約・ウォークイン) |
| `/sns/store/<id>/drafts/` | SNS投稿の下書き確認・承認 |
| `/inventory/store/<id>/` | 在庫一覧・入荷登録・発注案 |
| `/admin/` | マスタ管理(座席・シフト・チェックリスト雛形・商品・テンプレート等) |

## テストする

```
coverage run --source='.' manage.py test
coverage report -m
```
