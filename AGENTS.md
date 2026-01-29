# AI Agent Instructions for Jules

## コーディング原則とガイドライン

### 1. 使用言語

- **日本語を第一言語とする**: Gitのコミットメッセージ、Pull Requestのタイトル・説明、コード内のコメント、およびユーザー（開発者）との対話は、すべて日本語で行ってください。
- 英語の使用箇所: 変数名、関数名、クラス名、および外部ライブラリのエラーメッセージの引用などに限定します。

### 2. コメントとドキュメンテーション

- **新人エンジニア向けの丁寧なコメント**:
  - **What (何をしているか)**: 処理の流れがわかるように記述します。
  - **Why (なぜしているか)**: 設計判断、特定のライブラリ使用の理由、複雑な処理の意図を記述します。
- **シーケンス図の活用**: 処理フローが複雑な場合は、Mermaid形式でシーケンス図を作成し、`docs/` 配下に保存してください。

### 3. アーキテクチャと設計パターン

このプロジェクトは **Clean Architecture** を採用しています。

- **Core (Domain/Use Cases)**: ビジネスロジック。外部フレームワーク（Flask, LINE SDKなど）に依存しないようにします。
- **Interfaces (Controllers/Gateways)**: 外部との境界。アダプターパターンを使用して外部依存を吸収します。
- **Infrastructure (Main/Config)**: エントリーポイントと設定。依存性の注入（DI）を行います。

#### 具体的な実装の工夫（Tricks）:

- **Cloud Functionsの非同期対応**: `functions-framework` は同期的なエントリーポイントを要求するため、`asgiref.sync.async_to_sync` を使用して `main` 関数（同期）から `main_logic` 関数（非同期）を呼び出すブリッジパターンを採用しています。
- **Gemini Function Callingの型変換**: Google GenAI SDKはツールの引数を `MapComposite` などのProtobuf型で渡してくることがあります。これを標準のPython `dict` / `list` に変換するサニタイズ処理 (`GeminiAdapter._sanitize_arg`) を実装しています。
- **Notionプロパティの抽象化**: AIにはデータベースの「論理名（英語キー）」のみを教え、内部でAdapterが実際のDatabase ID（UUID）に変換します。また、`schemas.yaml` を用いてプロパティ型を管理し、適切なAPIペイロードを生成します。

### 4. 開発・テスト

- **事前の検証**: コードを変更した後は、必ず `ls`, `read_file`, `grep` などの読み取り専用ツールで変更が正しく適用されたか確認してください。
- **テストの実行**: `python -m pytest tests/` を実行して、リグレッションがないか確認してください。

### 5. 構成管理

- **English Keys / Japanese Logic**: コード上の識別子やYAMLのキーは英語を使用しますが、ユーザー向けの表示やAIへの指示（プロンプト）、コメントは日本語を使用します。
- **English Keys / Japanese Logic**: コード上の識別子やYAMLのキーは英語を使用しますが、ユーザー向けの表示やAIへの指示（プロンプト）、コメントは日本語を使用します。
- **設定ファイル**: `schemas.yaml` は廃止され、Firestore (`notion_schemas` コレクション) に移行しました。開発時は `firestore_import_data/notion_schemas/*.json` を編集し、GitHub Actions経由でデプロイします。

### 6. 主要機能と設計判断 (Design Decisions)

#### A. E-paper ToDo Display

- **構成**: Cloud Functions (`/api/todo_list`) + Raspberry Pi Client (Docker)。
- **データフロー**: Notion -> Cloud Functions (API) -> Raspberry Pi (Pillowで画像生成) -> Waveshare E-paper。
- **選定理由**:
  - API側でJSONを返す形式にした理由: クライアント側（ラズパイ）での描画の柔軟性を高めるため。また、将来的に別のディスプレイ端末（M5Paperなど）に対応しやすくするため。
  - Pillowによるサーバーサイド（今回の実装ではクライアントサイドだがロジックは分離）描画: E-paperは描画更新に時間がかかるため、画像生成ロジックは切り離し、表示デバイス上では「画像を表示するだけ」にするのが理想的だが、今回はラズパイの処理能力を活かしてクライアント内で生成する構成を採用。

#### B. Gemini Grounding (Search Integration)

- **目的**: ユーザーがタスクを入力した際、詳細情報（場所、開催期間など）を自動補完する。
- **実装**: `google_search_retrieval` ツールを使用。
- **設計**: 直接Google Custom Search APIを叩くのではなく、GeminiのGrounding機能を使用することで、検索クエリの生成から結果の要約までをLLMに任せ、実装コストを低減。

#### C. Raspberry Pi Client (Docker)

- **特記事項**: `waveshare-epd` ライブラリは `pip` install できない（setup.py installが必要）ため、Dockerfile内で `git clone` してインストールする戦略を採用。
- **ハードウェアアクセス**: `privileged: true` と `/dev/snd` のマウントが必要。
- **テスト**: Mockモード (`--mock`) を実装し、実機がなくても画像生成ロジックを検証可能にしている。

### 7. ドキュメント構成 (`docs/`)

- **architecture.md**: システム全体図。
- **functions.md**: Cloud Functionsの詳細仕様。
- **spec_epaper_todo.md**: E-paper機能の仕様書（Artifactから移行推奨）。
- **walkthrough.md**: 検証記録とセットアップ手順（最新手順はここ）。
