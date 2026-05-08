# ワクチン・予防接種ダッシュボード（試行版）

GitHub Pages + GitHub Actions で動く、ワクチン・予防接種関連情報のモニタリング用ダッシュボードです。

## 今回の更新

- 上部の「現在の注目点」を、**テキスト要約なしの文献数サマリー**に簡素化
  - 何日時点の集計かが分かるように表示
  - Academic papers / Peer-reviewed / Preprints の件数のみ表示
- 各カードから `Original` と `Copy summary` ボタンを削除
  - タイトルのリンクから原文へ遷移する構成に整理
- 日本語訳の品質改善
  - 翻訳キャッシュのバージョンを更新し、次回実行時に再翻訳
  - ワクチン・予防接種関連語の用語補正を追加
  - 行政文書・会議案内由来の不要文が要約に入りにくいよう調整
- 文献検索対象ジャーナルを拡張
  - JAMA Network / JAMA Pediatrics
  - Clinical Infectious Diseases / Journal of Infectious Diseases / OFID
  - Emerging Infectious Diseases
  - Pediatrics
  - PLOS journals
  - eClinicalMedicine / EBioMedicine
  - IJID / Clinical Microbiology and Infection
  - Vaccine: X
  - Cochrane Library
  - Journal of Travel Medicine
  - SSRN preprints
- Academicセクションは、査読付きジャーナルとプレプリントを中心に表示
- FDA SOPP、技術的手順書、ガイダンス一覧、食品リコール、biologics一般文書などは除外

## 反映方法

1. ZIPを展開し、既存リポジトリの中身に上書きアップロード
2. GitHubの `Actions` → `Update dashboard and deploy Pages` → `Run workflow`
3. 公開ページを `Ctrl + F5` で強制再読み込み
