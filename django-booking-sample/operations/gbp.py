"""Google ビジネスプロフィール(GBP)連携。

要件C-1の条件付き採用分。Business Profile API の利用承認が取れている場合のみ
動作し(GBP_ACCESS_TOKEN / GBP_LOCATION を設定)、未設定なら呼び出し側が
「手動更新リマインダー」へ格下げする(要件定義 §2-C の敵対的レビュー結論)。
"""
import json
import os
import urllib.request

API = 'https://mybusinessbusinessinformation.googleapis.com/v1'


def is_configured():
    return bool(os.environ.get('GBP_ACCESS_TOKEN') and os.environ.get('GBP_LOCATION'))


def sync_special_hours(business_day):
    """臨時営業時間を GBP の specialHours に反映する。

    失敗時は例外を投げる(open_store が警告タスクに変換する)。
    """
    token = os.environ['GBP_ACCESS_TOKEN']
    location = os.environ['GBP_LOCATION']  # 例: locations/1234567890
    date = business_day.date
    payload = {
        'specialHours': {
            'specialHourPeriods': [{
                'startDate': {'year': date.year, 'month': date.month, 'day': date.day},
                'openTime': {'hours': business_day.opening_hour},
                'closeTime': {'hours': business_day.closing_hour},
            }]
        }
    }
    request = urllib.request.Request(
        f'{API}/{location}?updateMask=specialHours',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        method='PATCH',
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())
