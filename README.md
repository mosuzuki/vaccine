# Vaccine and Immunization Monitoring

GitHub Pages + GitHub Actions で動く、ワクチン・予防接種の政策、研究開発、コミュニケーションに関するグローバル監視ダッシュボードです。

## 目的
最新のワクチン・予防接種関連情報を、次の3領域でピックアップします。
- Policy
- Research and development
- Communication

## 情報源
- Tier 1: WHO, CDC, ECDC, FDA などの国際機関・保健当局の公式情報
- Tier 2: Reuters, AP, BBC, Financial Times, STAT, Nature News, Science, NHK, 日経, 共同 など
- Tier 3: Lancet, NEJM, BMJ, Nature / npj Vaccines など

## 使い方
1. GitHub の `Settings > Pages` で Source を **GitHub Actions** にする
2. `Actions > Update dashboard and deploy Pages > Run workflow` を実行
3. 公開サイトを開く

## 主な機能
- 記事の日本語表示
- Policy / Research / Communication 自動分類
- policy tag 自動分類
- vaccine type 自動分類
- variant 抽出
- 類似タイトル重複除去
- 地図表示（既定は source origin、切替で target country）
