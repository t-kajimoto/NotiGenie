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

*   **Cloud Functions**: `main.py` がエントリーポイントです。アーキテクチャの詳細は後述の「コード品質とアーキテクチャ」セクションを参照してください。
*   **Raspberry Pi**: ハードウェア依存（マイク、スピーカー）が強いため、ロジック変更時はモックテストを活用してください。
*   **言語**: プラン提示やコミットメッセージは日本語を使用してください。

## コード品質とアーキテクチャ (Code Quality & Architecture)

### 1. クリーンアーキテクチャ (Clean Architecture)
本プロジェクトの `cloud_functions/` は、クリーンアーキテクチャの原則に基づいて構成されています。
変更を加える際は、以下のレイヤー構成を維持してください。

*   **Core (Domain & Use Cases)**:
    *   `core/domain`: 外部に依存しない純粋なインターフェース定義（Entities/Interfaces）。
    *   `core/use_cases`: ビジネスロジック（アプリケーションの振る舞い）。
*   **Infrastructure (Adapters & Drivers)**:
    *   `core/interfaces/gateways`: 外部サービス（Gemini, Notion）へのアダプター実装。
    *   `core/interfaces/controllers`: 入力（LINE, HTTP）をユースケースに変換するコントローラー。
    *   `main.py`: エントリーポイント。Dependency Injectionを行い、レイヤーを結合します。

### 2. コメント (Comments)
初学者でも理解できるように、コードには以下のコメントを充実させてください。
*   **Docstrings**: クラスやメソッドの役割、引数、戻り値を明確に記述する。
*   **Inline Comments**: 「なぜそうするのか（Why）」、「何をしているのか（What）」を丁寧に説明する。特にアーキテクチャ上の意図（DI、Interfaceなど）や非同期処理については詳しく記述する。

### 3. Linter
コードの品質を保つため、`flake8` を使用して構文チェックを行ってください。
