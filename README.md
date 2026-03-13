# ワクチン・予防接種ダッシュボード（試行版）

GitHub Pages + GitHub Actions で動くダッシュボードです。

## 今回の更新
- タイトルを `ワクチン・予防接種ダッシュボード（試行版）` に変更
- 直近14日間に限定
- 対象を **研究開発 / 予防接種政策 / ワクチンコミュニケーション** に限定
- 信頼できる一次ソース中心（official / academic / preprint）
- 記事全文取得 (`trafilatura`) を優先し、取得できない場合はRSS summaryにフォールバック
- AI要約を日本語表示
- 目的外ページ（ハブ、一覧、血液製剤・機器・一般FAQ等）を厳格除外
- タイトル・要約の重複除外を強化
- Feed Status を画面下部に小さく表示

## 反映方法
1. 既存リポジトリにこのZIPの中身を上書きアップロード
2. `Actions` → `Update dashboard and deploy Pages` → `Run workflow`
3. 必要なら公開ページを `Ctrl+F5` で強制再読み込み

- ソースに CIDRAP、New York Times、The Guardian、Washington Post、NHK、日経、朝日、読売、毎日などの主要メディア監視を追加
