# AGENTS.md

このファイルは、AIエージェント（Julesなど）がこのプロジェクトを理解し、開発・テストを行うためのガイドラインです。

## プロジェクト概要

NotiGenieは、Raspberry Pi上で動作し、Cloud Functions上のバックエンドを経由してNotionを操作するアプリケーションです。

## アーキテクチャ

`docs/architecture.md` を参照してください。
主な構成要素:
- **Cloud Functions (`cloud_functions/`)**: Geminiを使用した意図解析、Notion操作のロジック。
- **Raspberry Pi (`raspberry_pi/`)**: 音声入出力、STT、TTS。

## 環境構築と実行手順 (Jules環境用)

### 1. 依存関係のインストール

テストに必要なライブラリをインストールします。

```bash
pip install -r cloud_functions/requirements.txt
# Raspberry Pi用のライブラリはLinux環境(x86)では一部インストール困難な場合があるため、テスト実行に必要なもののみ適宜インストールします。
# テスト用
pip install pytest pytest-asyncio pytest-mock
```

### 2. 設定ファイルの準備

`cloud_functions/config.yaml` は既に `src/config.yaml.example` から移動されています。
`.env` (または環境変数) でAPIキーを設定します（テスト時はダミーで可）。

```bash
export GEMINI_API_KEY="dummy"
export NOTION_API_KEY="dummy"
```

### 3. テストの実行

`pytest` を使用して、Cloud Functionsのロジックと、Raspberry Piのクライアントロジック（モックベース）のテストを行います。

```bash
pytest tests/
```

### 開発ガイドライン

*   **Cloud Functions**: `main.py` がエントリーポイントです。`gemini_agent.py` と `notion_handler.py` にロジックを集約します。
*   **Raspberry Pi**: ハードウェア依存（マイク、スピーカー）が強いため、ロジック変更時はモックテストを活用してください。
*   **言語**: プラン提示やコミットメッセージは日本語を使用してください。
