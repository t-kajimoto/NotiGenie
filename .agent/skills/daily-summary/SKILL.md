---
description: NotiGenieのその日の会話履歴とアクティビティ（Notion更新、エラーログ）を要約して確認するスキル
---

# Daily Summary Fetcher

このスキルは、NotiGenieシステムに関連する以下のデータソースから、**当日分**のアクティビティを取得し、ユーザーとの会話やシステムの稼働状況を把握するために使用します。

1.  **Cloud Logging (Cloud Run / Functions)**: システムのエラーログやアプリケーションログ（`resource.type="cloud_function"` または `resource.type="cloud_run_revision"`）。
2.  **Notion**: 更新されたページ（ユーザーが追加したToDoやメモなど）。
3.  **Firestore**: 会話履歴（`conversations` コレクション）。
    - _注意_: Firestoreへのアクセスには有効な `GOOGLE_APPLICATION_CREDENTIALS` (JSONファイル) が必要です。

## 使用方法

以下のコマンドを実行して、データを取得・保存します。

```powershell
# 仮想環境が有効であることを確認してください
# 必要なライブラリ: google-cloud-firestore, notion-client, google-cloud-logging (gcloud CLI経由で取得するため不要だがSDKは必要)

python .agent/skills/daily-summary/fetch_daily_summary.py
```

実行後、カレントディレクトリに `daily_summary_report.json` が生成されます。
このJSONファイルの内容を読み取って、ユーザーに報告してください。

## 依存関係と設定

### 1. 環境変数 (.env)

プロジェクトルートの `.env` ファイルに以下が設定されている必要があります。

- `NOTION_API_KEY`: Notionインテグレーションキー
- `GOOGLE_APPLICATION_CREDENTIALS`: サービスアカウントキーのJSONファイルパス (Firestore用)

### 2. Google Cloud SDK (gcloud)

Cloud Loggingの取得には `gcloud` コマンドを使用します。
Windows環境では、スクリプトが自動的に `gcloud` コマンドのパスを探そうとしますが、パスが通っていることを推奨します。

### 3. Pythonライブラリ

プロジェクトの仮想環境で以下がインストールされている必要があります。

```bash
pip install google-cloud-firestore notion-client python-dotenv
```

## トラブルシューティング

- **Firestoreのエラー**: `Invalid JWT Signature` などのエラーが出る場合は、サービスアカウントキーが期限切れか無効です。
- **gcloudのエラー**: `gcloud auth login` や `gcloud config set project notigenie` が正しく設定されているか確認してください。

## スクリプトの場所

`.agent/skills/daily-summary/fetch_daily_summary.py`
