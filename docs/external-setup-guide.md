# 外部サービス設定手順書(アカウント所有者が行う作業)

コードは全フェーズ実装済み。ここに挙げる作業だけは各サービスのアカウント所有者本人にしか
できないため、手順として整理する。**すべて任意**であり、未設定の間も各機能は
手動フォールバック(コピペ投稿・手動更新リマインダー・発注書テキスト)で動作する。

## 1. GCP デプロイ(Cloud Run)

前提: gcloud CLI インストール済み、課金有効な GCP プロジェクト。

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>

# シークレット登録
python -c "import secrets; print(secrets.token_urlsafe(50))" | \
  gcloud secrets create django-secret-key --data-file=-

# デプロイ(リポジトリの django-booking-sample/ で実行)
gcloud run deploy booking --source . --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars DJANGO_DEBUG=false,DJANGO_ALLOWED_HOSTS=<デプロイ後のホスト名> \
  --set-secrets DJANGO_SECRET_KEY=django-secret-key:latest
```

- DB: 本番は Cloud SQL(PostgreSQL)を推奨。`DATABASES` の環境変数化は導入時に対応。
- 画像の公開ホスティング(Instagram 投稿の前提):

```bash
gsutil mb -l asia-northeast1 gs://<BUCKET>
gsutil iam ch allUsers:objectViewer gs://<BUCKET>
# 環境変数に PUBLIC_MEDIA_BASE_URL=https://storage.googleapis.com/<BUCKET> を設定し、
# DJANGO_MEDIA_ROOT を GCS マウント(Cloud Run volume)に向ける
```

- 開店前ジョブを定時実行したい場合は Cloud Scheduler → 認証付きで任意のエンドポイントを叩く
  (現状は開店操作を人間がダッシュボードで行う設計なので必須ではない)。

## 2. Threads API(最優先・審査が軽い)

1. https://developers.facebook.com でアプリ作成 → ユースケース「Threads API」を追加
2. 投稿したい Threads アカウントでアプリを承認し、長期アクセストークンを取得
3. 環境変数を設定: `THREADS_ACCESS_TOKEN`、`THREADS_USER_ID`

## 3. Instagram Graph API(Meta アプリレビューが必要)

1. Instagram をプロアカウント(ビジネス)化し、Facebook ページと接続
2. Meta 開発者アプリに Instagram Graph API を追加
3. アプリレビューで `instagram_basic` と `instagram_content_publish` を申請
   - 申請文例: 「自店舗の開店告知(出勤情報・入荷情報)を、店長の承認操作を経て
     自動投稿する店舗管理システムです。スクリーンキャストは /sns/ の承認画面を提出」
4. 承認後、長期トークンを取得し設定: `IG_ACCESS_TOKEN`、`IG_USER_ID`
5. `PUBLIC_MEDIA_BASE_URL` の設定が必須(画像は公開URLでしか渡せない)

## 4. X (Twitter) API

- 判断事項: **無料枠(月間投稿数が少なく仕様変更が頻繁)で足りるか、Basic プラン(有料)を契約するか**。
  1日1〜2投稿なら無料枠でも収まる場合があるが、上限・条件は頻繁に変わるため契約前に最新の
  https://developer.x.com/en/portal/products を確認すること。
- 手順: developer portal でアプリ作成 → OAuth1.0a のキー4種を取得 → 環境変数
  `X_CONSUMER_KEY` / `X_CONSUMER_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` を設定。
- ライブラリ(requests-oauthlib)は導入済み。キーを入れるだけで動く。

## 5. Google ビジネスプロフィール API

1. ビジネスプロフィールのオーナー確認を済ませる
2. https://developers.google.com/my-business から **API利用申請**(承認制。数週間かかる/否認もある)
3. 承認されたら OAuth でトークンを取得し設定: `GBP_ACCESS_TOKEN`、`GBP_LOCATION`(`locations/<ID>` 形式)
- 否認された場合はそのままでよい(臨時営業時間のある日に手動更新リマインダーが出る設計)

## 6. 発注メール(SMTP)

任意の SMTP(Gmail のアプリパスワード、SendGrid 等)で以下を設定:

```
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_HOST_USER=...
DJANGO_EMAIL_HOST_PASSWORD=...
DJANGO_DEFAULT_FROM_EMAIL=order@example.com
```

未設定でも発注書テキストが画面に出るので、電話/FAX/LINE 運用は可能。

## 優先順位の推奨

1. GCP デプロイ(まず店内業務=Phase 1 の価値が出る)
2. Threads(審査が軽く、SNS自動投稿の効果検証ができる)
3. SMTP(発注メール)
4. Instagram(レビュー待ちの間は手動コピペ運用)
5. X(有料化の判断を効果検証後に)
6. GBP(承認が取れたら)
