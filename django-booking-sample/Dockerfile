# Cloud Run 用コンテナ(要件C-3)。
# デプロイ例:
#   gcloud run deploy booking --source . --region asia-northeast1 \
#     --set-env-vars DJANGO_DEBUG=false,DJANGO_ALLOWED_HOSTS=<host> \
#     --set-secrets DJANGO_SECRET_KEY=django-secret-key:latest
# 画像などのメディアは Cloud Storage を PUBLIC_MEDIA_BASE_URL で公開する
# (Instagram 投稿は公開URL必須のため)。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# SNS投稿画像の日本語描画用フォント(sns/imaging.py が探索するパスに入る)
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# 本番イメージは DEBUG オフがデフォルト。DJANGO_SECRET_KEY 未設定なら起動時に失敗する(フェイルセーフ)
ENV DJANGO_DEBUG=false
ENV PORT=8080
CMD exec gunicorn project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4
