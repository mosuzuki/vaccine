# Global Vaccine Policy Monitor

GitHub Pages + GitHub Actions で動く、世界のワクチン・予防接種政策ニュースの監視ダッシュボードです。

## 特徴
- Tier 1: WHO / CDC / ECDC / FDA など公的機関を最優先
- Tier 2: Reuters / AP / BBC / FT / STAT / Nature News / Science / 日経 / NHK / 共同通信 などの信頼できる主要メディアを優先
- Tier 3: Lancet / NEJM / BMJ / Nature / npj Vaccines など学術系を補助的に収集
- 日本語自動翻訳
- 政策タグ自動分類
- 重複ニュース統合
- 地図表示（発信元所在地 / ニュース対象国の切替）

## 使い方
1. GitHub リポジトリに全ファイルを置く
2. Settings > Pages で Source = GitHub Actions
3. Actions > Update dashboard and deploy Pages > Run workflow
4. 公開URLで確認

## 調整
- 取得元は `scripts/config.json`
- 収集ロジックは `scripts/fetch_news.py`
- 表示は `assets/app.js`
