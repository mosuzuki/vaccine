# Vaccine & Immunization News Dashboard

GitHub Pages + GitHub Actions で動く、ワクチン・予防接種ニュース専用ダッシュボードです。

## できること
- 毎日自動でニュース取得
- `data/news.json` を自動更新
- GitHub Pages でそのまま公開
- ソース、地域、トピック、キーワードで絞り込み
- 重複しやすい記事を正規化ルールで自動除外
- 直近7日・30日の件数サマリー表示

## 主なソース
- CDC media RSS
- FDA press releases / biologics RSS
- ECDC news RSS
- EMA news RSS
- UNICEF news RSS
- Google News RSS（公式・高信頼ドメインに絞った補助検索）

## 使い方
1. この一式を新しい GitHub リポジトリに push
2. `Settings > Pages > Build and deployment` で **Source = GitHub Actions**
3. `Actions` タブで `Update dashboard and deploy Pages` を一度手動実行
4. 公開URL:
   `https://<your-user>.github.io/<repo>/`

## 更新時刻
`.github/workflows/update-news.yml` の cron は UTC 基準です。  
現在は `10 21 * * *` なので **毎日 JST 06:10** に実行されます。

## カスタマイズ
- RSSソース: `scripts/config.json`
- 表示UI: `index.html`, `assets/app.js`, `assets/style.css`
- 取得ロジック: `scripts/fetch_news.py`

## 注意
- GitHub Pages は静的サイトです。APIキーを埋め込む設計にはしていません。
- Google News RSS は補助用途です。一次情報や規制当局・公衆衛生機関の公式ソースを優先しています。
