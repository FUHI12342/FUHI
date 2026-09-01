# CLAUDE.md — プロジェクト案内(AI・人間共通)

## これは何か
占い・飲食店の予約サイト(Django)を「リアル店舗の開店業務自動化システム」に拡張したもの。
アプリ本体は `django-booking-sample/`、設計・運用資料は `docs/`。

## まず読む資料(順番)
1. `docs/store-opening-automation-requirements.md` — 要件・見送り判断・実装済み管理表
2. `docs/operations-model.md` — 権限マトリクス・日次運用・障害時フォールバック
3. `docs/backlog.md` — 未着手タスク(GitHub Issues と対応)
4. `docs/handoff.md` — **進行中作業の引き継ぎ**(コンテキストクリア後はここから再開)
5. `docs/external-setup-guide.md` — アカウント所有者にしかできない外部設定

## 開発コマンド(`django-booking-sample/` で実行)
```
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo   # デモ: demo / demo12345
python manage.py runserver
python manage.py test                                    # 全テスト(CI と同じ)
```

## アプリ構成と責務
| アプリ | 責務 | 主要モジュール |
|---|---|---|
| booking | 店舗・スタッフ・座席・予約、**共通基盤** | `access.py`(権限/機能フラグ判定の唯一の場所)、`timeslots.py`(営業日枠⇔実時刻) |
| operations | 営業日・開店チェックリスト・開店連鎖シグナル・GBP | `services.open_store`、`signals.store_opened`、`receivers.py` |
| attendance | シフト・打刻・月次CSV | `Shift.objects.publishable_casts`(SNS掲載可の出勤者) |
| sns | 下書き生成→店長承認→配信、アダプタ | `services.py`、`adapters.py`、`imaging.py` |
| inventory | 商品・入出庫・発注案→承認→送信 | `services.py`、`receivers.py` |

## 守るべき設計ルール
- **無人で対外確定しない**: SNS投稿・発注は必ず店長(`Staff.is_manager`)の承認操作を挟む
- **権限判定は `booking/access.py` のみ**: ビューは `check_store_access()` / `StoreAccessMixin` を使う
- **機能フラグ**(`Store.enable_*`)オフの機能は 404 + 開店連鎖から除外
- **時刻は営業日基準**: 24以上は翌日早朝(25=翌1時)。変換は `booking/timeslots.py` 経由
- **開店連鎖の失敗は握りつぶさない**: レシーバの例外は `open_store` が警告タスク化する
- **SNS掲載は `publishable_casts`(在籍中×掲載可)のみ**。退職者は削除せず `is_on_roster=False`

## ブランチ・マージ運用
- 作業ブランチ: `claude/store-opening-automation-bok4kj`(マージ後は main から作り直す)
- CI(GitHub Actions)グリーンを確認してから PR → main へマージ
- コミットは日本語で「何を・なぜ」。テスト件数を明記
