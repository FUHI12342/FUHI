"""SNSプラットフォームごとの投稿アダプタ。

設計方針(要件 B-4):
- 認証情報が未設定のプラットフォームは「手動フォールバック」(manual)になり、
  生成済みの文面と画像を人間がコピペ投稿する。API が使えなくても機能全体は成立する。
- 実際の API 呼び出しは承認操作の中でのみ行われる。無人実行はしない。
"""
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    pass


class BaseAdapter:
    platform = 'base'

    def is_configured(self):
        raise NotImplementedError

    def publish(self, body, image_url=None):
        """投稿して投稿URL(または識別子)を返す。失敗時は AdapterError。"""
        raise NotImplementedError

    @staticmethod
    def _post_json(url, payload=None, data=None, timeout=20):
        if payload is not None:
            data = json.dumps(payload).encode()
            headers = {'Content-Type': 'application/json'}
        else:
            data = urllib.parse.urlencode(data or {}).encode()
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            raise AdapterError(str(e)) from e


class ThreadsAdapter(BaseAdapter):
    """Threads API(コンテナ作成 → publish の2段階)。"""
    platform = 'threads'
    API = 'https://graph.threads.net/v1.0'

    def __init__(self):
        self.token = os.environ.get('THREADS_ACCESS_TOKEN', '')
        self.user_id = os.environ.get('THREADS_USER_ID', '')

    def is_configured(self):
        return bool(self.token and self.user_id)

    def publish(self, body, image_url=None):
        params = {'access_token': self.token, 'text': body}
        if image_url:
            params.update(media_type='IMAGE', image_url=image_url)
        else:
            params['media_type'] = 'TEXT'
        container = self._post_json(f'{self.API}/{self.user_id}/threads', data=params)
        result = self._post_json(
            f'{self.API}/{self.user_id}/threads_publish',
            data={'access_token': self.token, 'creation_id': container.get('id', '')},
        )
        return f"https://www.threads.net/post/{result.get('id', '')}"


class InstagramAdapter(BaseAdapter):
    """Instagram Graph API。画像は公開URL必須(Cloud Storage等でホストする)。"""
    platform = 'instagram'
    API = 'https://graph.facebook.com/v21.0'

    def __init__(self):
        self.token = os.environ.get('IG_ACCESS_TOKEN', '')
        self.user_id = os.environ.get('IG_USER_ID', '')

    def is_configured(self):
        return bool(self.token and self.user_id)

    def publish(self, body, image_url=None):
        if not image_url:
            raise AdapterError('Instagram は画像必須です(公開URLでホストされている必要があります)')
        container = self._post_json(
            f'{self.API}/{self.user_id}/media',
            data={'access_token': self.token, 'image_url': image_url, 'caption': body},
        )
        result = self._post_json(
            f'{self.API}/{self.user_id}/media_publish',
            data={'access_token': self.token, 'creation_id': container.get('id', '')},
        )
        return f"https://www.instagram.com/p/{result.get('id', '')}"


class XAdapter(BaseAdapter):
    """X API v2。無料枠は制限が厳しいため、未設定運用(手動フォールバック)を標準とする。

    OAuth1.0a の署名が必要なため、利用時は requests-oauthlib の導入を前提とする。
    未導入・未設定なら is_configured() が False になり manual にフォールバックする。
    """
    platform = 'x'

    def __init__(self):
        self.consumer_key = os.environ.get('X_CONSUMER_KEY', '')
        self.consumer_secret = os.environ.get('X_CONSUMER_SECRET', '')
        self.access_token = os.environ.get('X_ACCESS_TOKEN', '')
        self.access_secret = os.environ.get('X_ACCESS_TOKEN_SECRET', '')

    def is_configured(self):
        if not all([self.consumer_key, self.consumer_secret, self.access_token, self.access_secret]):
            return False
        try:
            import requests_oauthlib  # noqa: F401
        except ImportError:
            logger.warning('X_* が設定されていますが requests-oauthlib が未導入のため手動フォールバックします')
            return False
        return True

    def publish(self, body, image_url=None):
        from requests_oauthlib import OAuth1Session
        session = OAuth1Session(
            self.consumer_key, self.consumer_secret, self.access_token, self.access_secret
        )
        response = session.post('https://api.x.com/2/tweets', json={'text': body}, timeout=20)
        if response.status_code >= 300:
            raise AdapterError(f'X API error {response.status_code}: {response.text[:200]}')
        tweet_id = response.json().get('data', {}).get('id', '')
        return f'https://x.com/i/web/status/{tweet_id}'


def get_adapters():
    """有効なプラットフォームのアダプタ一覧。テストから差し替え可能にするため関数化。"""
    return [ThreadsAdapter(), XAdapter(), InstagramAdapter()]
