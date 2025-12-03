# NotiGenie
Notionと音声で連携するアプリ

## アーキテクチャ (v1.1)
Raspberry Pi と Cloud Functions を組み合わせたアーキテクチャを採用しています。
詳細は `docs/architecture.md` を参照してください。

### ディレクトリ構成
- `cloud_functions/`: バックエンドロジック (LINE Bot, Notion API, Gemini)
- `raspberry_pi/`: クライアントロジック (Wake Word, STT, TTS)
- `docs/`: 設計ドキュメント

### セットアップ

#### Cloud Functions
`cloud_functions/` ディレクトリ配下をデプロイします。
`config.yaml` でNotionデータベースのマッピングを定義します。

環境変数として以下が必要です：
- `GEMINI_API_KEY`: Google Gemini APIキー
- `NOTION_API_KEY`: Notion Integration Token
- `LINE_CHANNEL_ACCESS_TOKEN`: (Optional) LINE Bot用
- `LINE_CHANNEL_SECRET`: (Optional) LINE Bot用

#### Raspberry Pi
`raspberry_pi/` ディレクトリ配下でアプリケーションを実行します。
`.env` ファイルに以下を設定してください：
- `PICOVOICE_ACCESS_KEY`: Picovoice Access Key
- `CLOUD_FUNCTIONS_URL`: デプロイしたCloud FunctionsのURL
- `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud Service Account Key (JSON path)

### テスト
`pytest` を実行して、ビジネスロジックのテストを行います。
