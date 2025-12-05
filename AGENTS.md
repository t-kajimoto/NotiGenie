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
- **設定ファイル**: `schemas.yaml` にデータベース定義を集約しています。`config.yaml` は廃止されました。
