# EBS Research Dashboard v2

GitHub Pages + GitHub Actions で動く、研究機関向け Event-Based Surveillance ダッシュボードです。

## 今回追加した機能

- 記事タイトルと要約の日本語訳表示
- 地図表示
- `variant / vaccine / outbreak` の自動分類
- 類似タイトルの重複統合
- 統合件数と統合元ソースの表示
- 原文確認用の `Original` 折りたたみ表示

## ファイル構成

```text
.github/workflows/update-news.yml   GitHub Actions
assets/app.js                       フロントエンド
assets/style.css                    スタイル
scripts/fetch_news.py               RSS取得・翻訳・分類・重複除去
scripts/config.json                 監視対象設定
data/news.json                      公開用データ
data/translation_cache.json         翻訳キャッシュ
index.html                          ダッシュボード本体
```

## GitHubで更新する方法

1. 既存のリポジトリのファイルをこのZIPの内容で上書きする
2. `.github/workflows/update-news.yml` が存在することを確認する
3. `Actions` タブを開く
4. `Update dashboard and deploy Pages` を選ぶ
5. `Run workflow` を押す

## メモ

- 日本語訳は GitHub Actions 実行時に自動生成します。翻訳に失敗した記事は原文のまま表示されます。
- 翻訳結果は `data/translation_cache.json` に保持されるため、毎回すべてを再翻訳しません。
- 重複除去は、国・分類・タイトル類似度をもとにしたルールベースです。
- 地図は `country_centroids` を使うため、都市単位の位置ではなく国・地域の代表点表示です。
