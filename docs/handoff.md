# 引き継ぎ(進行中作業)

最終更新: 2026-09-01 / ブランチ: `claude/store-opening-automation-bok4kj`(main = PR #11 マージ済み)

## 現在の作業: 全体リファクタリング(挙動変更なし、テスト122件が安全網)

### 完了
- [x] `booking/access.py` を共通アクセス制御層に拡張(`check_store_access`, `StoreAccessMixin`, 機能フラグ→404)
- [x] `booking/timeslots.py` 新設(`make_aware_datetime`, `business_slot`, `business_day_span`, `calendar_day_range`)
- [x] `booking/views.py` を上記ベースに書き直し

### 残り(この順で)
- [ ] `operations/views.py`, `sns/views.py`, `inventory/views.py`, `attendance/views.py` を access 層ベースに書き直し
- [ ] `sns/services.py`: 画像URL生成の重複を `_image_url()` に統合、`PUBLIC_MEDIA_BASE_URL` を settings 化
- [ ] `inventory/services.py`: 暦日範囲を `timeslots.calendar_day_range` に置換、`Coalesce` を明示 import
- [ ] 関数内 import の解消(`sns/imaging.py` glob、`operations/gbp.py` datetime、`attendance/views.py`)
- [ ] `project/settings.py` を整理(env ヘルパー、import を先頭に、セクション整理、`PUBLIC_MEDIA_BASE_URL`)
- [ ] `booking/tests.py`(836行)を `booking/tests/` パッケージに分割、テスト内の関数内 import を整理
- [ ] ドキュメント再構成: 要件定義書 §5 の変更履歴を `docs/CHANGELOG.md` へ移し、§5 を「実装済み管理表」に。`backlog.md` は未着手のみ(Issue リンク付き)
- [ ] 全テスト → コミット → push → CI → PR → マージ → この文書を「進行中なし」に更新

### 再開手順
```
cd django-booking-sample && python manage.py test   # まず現状がグリーンか確認
git log --oneline -5                                 # どこまでコミット済みか
```
