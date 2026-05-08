# ワクチン・予防接種ダッシュボード（試行版）

GitHub Pages + GitHub Actions で動く、ワクチン・予防接種領域のモニタリングダッシュボードです。

## 今回の更新

- 研究者・政策担当者向けの落ち着いたデザインに刷新
- 上部に Executive summary を追加
  - Policy / Academic 件数
  - 頻出ワクチン分類
  - 注目候補の自動表示
- 画面構成を以下に整理
  - 左側：Policy / 予防接種政策
    - 上段：国内
    - 下段：海外
  - 右側：Academic / 学術論文
    - 査読付きジャーナルとプレプリントのみ
- Academic に論文タイプの自動ラベルを追加
  - VE
  - Safety
  - Immunogenicity
  - Clinical trial
  - Epi/burden
  - Modelling/CEA
  - Policy-relevant
- 各カードに「掲載理由」と信頼度ラベルを表示
- 各カードに `Copy summary` ボタンを追加
- FDA SOPP、技術的手順書、ガイダンス一覧、食品リコール、biologics一般文書などの除外条件を強化

## 反映方法

1. ZIPを展開し、既存リポジトリに中身を上書きアップロード
2. `Actions` → `Update dashboard and deploy Pages` → `Run workflow`
3. 公開ページを `Ctrl+F5` で強制再読み込み

