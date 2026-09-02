# バックログ(未着手タスク)

完了した項目は [CHANGELOG.md](CHANGELOG.md) に移した。ここには未着手のみ載せ、GitHub Issue と1対1で対応させる。
判定は **着手可能 / ブロック(判断・情報待ち) / 保留(要望ベース)** の3値。

## 着手可能

(なし。#4 顧客向けWeb座席予約は実装済み → [CHANGELOG.md](CHANGELOG.md))

## ブロック(オーナーの判断・情報が必要)

| Issue | 内容 | 待っているもの |
|---|---|---|
| [#5](https://github.com/FUHI12342/FUHI/issues/5) | X 投稿への画像添付 | X の契約プラン決定(プランで media upload の可否が変わる) |
| [#6](https://github.com/FUHI12342/FUHI/issues/6) | 発注書PDF(FAX向け) | FAX でしか受けない仕入先が実在するかの確認 |
| [#10](https://github.com/FUHI12342/FUHI/issues/10) | 外部サービス設定(GCP/Threads/SMTP/Meta/X/GBP) | アカウント所有者の作業(手順書あり) |

## 保留(運用が回ってから要望ベース)

| Issue | 内容 |
|---|---|
| [#7](https://github.com/FUHI12342/FUHI/issues/7) | 営業日レポート(チェックリスト完了率・実績サマリ) |
| [#8](https://github.com/FUHI12342/FUHI/issues/8) | 棚卸しモード画面 |
| [#9](https://github.com/FUHI12342/FUHI/issues/9) | SNS画像のプラットフォーム別最適化 |

## 見送り(実装前検証で棄却。理由は要件定義書 §4 の R-1〜R-8 と以下)

- **Instagram 画像の署名付きURL化**: IG は非同期に画像を取得するため短命URLは失敗リスクがある。公開バケット+推測困難なファイル名を維持
- **承認済みSNS投稿の取り下げ再投稿**: 各SNSの削除APIまで実装しないと不整合になる。誤投稿は各SNSで手動削除し、システムは同日二重投稿の防止(DB制約)までを責務とする
