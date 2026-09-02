# 引き継ぎ(進行中作業)

最終更新: 2026-09-02

## 進行中の作業: なし

Web(claude.ai/code)セッションでの作業はここまで。以降はローカル CLI(Claude Code)で続ける。
直近の成果は PR #12(全体リファクタリング + Issue #4 顧客向けWeb座席予約、146テスト)。履歴は [CHANGELOG.md](CHANGELOG.md)。

## ローカル CLI で再開する手順

```bash
git clone https://github.com/FUHI12342/FUHI.git && cd FUHI      # 既にあれば git pull origin main
git checkout -B claude/store-opening-automation-bok4kj origin/main # 作業ブランチは main から作り直す
cd django-booking-sample
python -m venv .venv && source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo             # デモ: demo / demo12345
python manage.py test                                              # 146件がグリーンなら再開OK
cd .. && claude                                                    # リポジトリ直下で起動(CLAUDE.md が自動で読まれる)
```

CLI で最初に伝えるとよいこと: 「CLAUDE.md と docs/handoff.md を読んでから、docs/backlog.md の状況を確認して」

## 次に着手するなら
- 着手可能な Issue は無い([backlog.md](backlog.md))。ブロック中の #5 / #6 / #10 はオーナー判断待ち:
  - #5 X 画像添付 → X の契約プラン決定後
  - #6 発注書PDF → FAX 仕入先の実在確認後
  - #10 外部サービス設定 → オーナー作業([external-setup-guide.md](external-setup-guide.md))
- 保留(要望ベース): #7 レポート / #8 棚卸しモード / #9 SNS画像最適化

## 運用ルールの要点(CLI でも同じ)
- CI グリーンを確認してから PR → main へマージ。マージ後はブランチを main から作り直す
- 権限判定は `booking/access.py`、時刻変換は `booking/timeslots.py` のみに置く(CLAUDE.md 参照)
