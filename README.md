# Vaccine & Immunization Policy Monitor

GitHub Pages + GitHub Actions で動く、世界各国のワクチン・予防接種政策ニュース監視ダッシュボードです。

## この版での主な変更
- Daily report と同系統の発想で、一次情報と高信頼メディアを中心に収集
- ワクチン／予防接種 + 政策キーワードで記事を絞り込み
- 日本語自動翻訳
- 地図表示は「ニュース対象国」を優先し、国が特定できない場合は情報発信元所在地を表示
- 発信元所在地に切り替えて表示することも可能
- policy tag を自動分類（推奨、スケジュール、承認、財政、安全性、流行対応など）
- 類似タイトル重複を統合

## デプロイ
1. 中身を既存リポジトリに上書き
2. `.github/workflows/update-news.yml` が存在することを確認
3. GitHub の `Settings > Pages` で `Source = GitHub Actions`
4. `Actions > Update dashboard and deploy Pages > Run workflow`

## 注意
- 収集元は RSS / Google News RSS ベースなので、将来 URL 変更の可能性があります
- 翻訳は自動処理なので、固有名詞などにぎこちなさが残る場合があります
- 「Daily report と完全に同じ」ソース一覧が別途ある場合は、`scripts/config.json` の `feeds` をその一覧に差し替えればそのまま使えます
