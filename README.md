# NotiGenie
Notionと音声で連携するアプリ

## アーキテクチャ移行中 (v1.1)
現在、Raspberry Pi と Cloud Functions を組み合わせた新しいアーキテクチャへ移行中です。
詳細は `docs/architecture.md` を参照してください。

### ディレクトリ構成
- `cloud_functions/`: バックエンドロジック (LINE Bot, Notion API, Gemini)
- `raspberry_pi/`: クライアントロジック (Wake Word, STT, TTS)
- `src/`: 旧ソースコード (移行完了後に削除予定)
