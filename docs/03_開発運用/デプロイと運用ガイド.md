# 開発・運用ガイド

## 1. 概要
このドキュメントは、本アプリケーションの開発、デプロイ、およびメンテナンスに必要な情報を提供します。

## 2. デプロイ手順 (Google Cloud Functions)

### 2.1. 推奨デプロイ方法: GitHub Actions
本プロジェクトでは、GitHub Actionsを用いた自動デプロイを推奨しています。`.github/workflows/deploy.yml` に定義されたワークフローにより、`main`ブランチの `cloud_functions/` ディレクトリ配下に更新があると、自動的にCloud Functionsにデプロイされます。

### 2.2. 必要なIAMロール
デプロイを実行するサービスアカウントには、以下のIAMロールが必要です。
- **Cloud Functions 管理者 (`roles/cloudfunctions.admin`)**: Cloud Functionsの作成、更新、削除。
- **サービス アカウント ユーザー (`roles/iam.serviceAccountUser`)**: Cloud Functionsの実行サービスアカウントとして自身を割り当てるため。
- **Cloud Run 管理者 (`roles/run.admin`)**: Gen2ファンクションの公開設定 (`--allow-unauthenticated`) に必要。
- **Firestore ユーザー (`roles/datastore.user`)**: 会話履歴とNotionスキーマの読み書きに必要。

### 2.3. 必要な環境変数
GitHubリポジトリのSecretsに以下の情報を登録してください。

| 変数名 | 説明 | 備考 |
|:---|:---|:---|
| `GCP_PROJECT_ID`| Google CloudプロジェクトID | |
| `GCP_SA_KEY` | デプロイ用サービスアカウントのJSONキー | Base64エンコードして登録 |
| `NOTION_API_KEY` | Notion Integration Token | |
| `GEMINI_API_KEY` | Google Gemini API キー | |
| `LINE_CHANNEL_ACCESS_TOKEN` | (任意) LINE Messaging API アクセストークン | |
| `LINE_CHANNEL_SECRET` | (任意) LINE Messaging API チャネルシークレット | |
| `FIRESTORE_DATABASE`| (任意) Firestore データベースID | 指定しない場合は `(default)` |

---

## 3. Notionデータベーススキーマの追加・更新
LLMが新しいNotionデータベースをツールとして利用できるようにするには、そのスキーマ情報をFirestoreに登録する必要があります。

### 3.1. Firestoreのデータ構造
- **コレクション**: `notion_schemas`
- **ドキュメントID**: `(任意、LLMが認識しやすい英語名)` 例: `todo_list`, `shopping_list`
- **フィールド**:
    - `db_id` (string): NotionデータベースのID (ハイフンなし)
    - `description` (string): このデータベースが何であるかの自然言語による説明 (LLMがいつ使うべきか判断するために重要)
    - `schema_json` (string): Notion APIから取得したデータベース情報のJSON文字列

### 3.2. スキーマ登録手順

#### ステップ1: Notionインテグレーションの準備
1. Notionで新しいデータベースを作成するか、既存のデータベースを開きます。
2. 右上の「…」メニューから「インテグレーション」を選択し、使用するインテグレーション（例: `NotiGenie`）を追加します。

#### ステップ2: データベースIDの取得
1. ブラウザでNotionデータベースを開きます。URLは `https://www.notion.so/{workspace_name}/{database_id}?v={view_id}` のような形式になっています。
2. `{database_id}` の部分がデータベースIDです。これをコピーします（ハイフンは削除してください）。

#### ステップ3: スキーマJSONの取得
1. Notion APIの `Get a database` エンドポイントを使用して、データベースのスキーマ情報を取得します。
   ```bash
   curl -X GET "https://api.notion.com/v1/databases/{database_id}" \
     -H "Authorization: Bearer {NOTION_API_KEY}" \
     -H "Notion-Version: 2022-06-28"
   ```
2. レスポンスとして返ってきたJSONオブジェクト全体をコピーします。

#### ステップ4: Firestoreへのデータ登録
1. [Google Cloud ConsoleのFirestore画面](https://console.cloud.google.com/firestore)にアクセスします。
2. `notion_schemas` コレクションを選択します。
3. 「ドキュメントを追加」をクリックします。
4. **ドキュメントID**に、LLMが識別しやすい名前（例: `meeting_minutes`）を入力します。
5. 以下の3つのフィールドを追加します。
   - `db_id`: (string) ステップ2で取得したID。
   - `description`: (string) データベースの説明を入力します。（例: `A database for storing meeting minutes.`）
   - `schema_json`: (string) ステップ3で取得したJSON文字列を貼り付けます。
6. 「保存」をクリックします。

以上で登録は完了です。次回のCloud Functionsの起動時（コールドスタート時）に新しいスキーマが自動的に読み込まれ、LLMがこのデータベースを操作対象として認識できるようになります。
