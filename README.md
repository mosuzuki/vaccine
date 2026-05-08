# ワクチン・予防接種ダッシュボード（試行版）

GitHub Pages + GitHub Actions で動く、ワクチン・予防接種関連情報のモニタリングダッシュボードです。

## 今回の更新

- 上部の「注目点」および文献数のみの表示を削除
- 代わりに「〇月〇日時点のAIサマリー」を追加
- AIサマリーは過去7日間の以下を対象に生成
  - Policy: 予防接種政策関連ニュース
  - Academic: 査読付きジャーナルおよびプレプリント
- GitHub Actions 実行時に `OPENAI_API_KEY` が設定されていれば、OpenAI APIで短い日本語サマリーを生成
- `OPENAI_API_KEY` が未設定、またはAPI実行に失敗した場合でも、ダッシュボード本体は表示されるように防御的に実装

## GitHub Secrets の設定

AIサマリーを有効化するには、リポジトリの以下に `OPENAI_API_KEY` を登録してください。

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Name:

```text
OPENAI_API_KEY
```

Value:

```text
OpenAI APIキー
```

## 反映方法

1. ZIPを展開し、中身を既存リポジトリに上書きアップロード
2. GitHub の `Actions` から `Update dashboard and deploy Pages` を手動実行
3. 公開ページを `Ctrl + F5` で強制再読み込み

