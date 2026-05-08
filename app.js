# ワクチン・予防接種ダッシュボード（試行版）

GitHub Pages + GitHub Actions で動くダッシュボードです。

## 今回の画面更新

- 一番上の地図表示を削除
- Leaflet の CSS / JavaScript 読み込みを削除
- 画面を「国内」と「海外」の2カラムに再構成
- 各カラムの上段に「予防接種政策関係ニュース」を表示
- 各カラムの下段に「学術論文ピックアップ」を表示
- 検索、期間、ワクチン種別のフィルターは維持
- Feed Status は通常は折りたたみ表示に変更

## 反映方法

1. このZIPの中身を既存リポジトリに上書きアップロード
2. `Actions` → `Update dashboard and deploy Pages` → `Run workflow`
3. 公開ページを `Ctrl+F5` で強制再読み込み

## 主な差し替えファイル

- `index.html`
- `assets/app.js`
- `assets/style.css`

`data/` と `scripts/` も同梱していますが、今回の主変更は表示側です。
