# デプロイ手順書

本プロジェクトのバックエンド（Cloud Functions）のデプロイ手順について記述します。

## 推奨されるデプロイ方法

**GitHub Actions** を使用した自動デプロイを推奨します。

### 理由
1. **リポジトリ統合**: ソースコード管理と同じ場所でCI/CDを管理でき、ワークフローが可視化しやすい。
2. **既存構成**: 既に `.github/workflows/deploy.yml` が用意されており、導入コストが低い。
3. **コスト**: GitHub Actionsの無料枠（通常月2000分）で十分運用可能である場合が多い。Cloud Buildはビルド時間に応じた課金が発生する（無料枠あり）。

---

## 必要な環境変数・シークレット

デプロイおよび実行には以下の環境変数が必要です。GitHub Actionsを使用する場合、これらをGitHubリポジトリの `Settings > Secrets and variables > Actions` に登録してください。

| 変数名 | 説明 | 備考 |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | Google Cloud Service Account のJSONキー | Cloud FunctionsおよびCloud Run管理者権限を持つサービスアカウントのキー |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API アクセストークン | LINE Developersコンソールから取得 |
| `LINE_CHANNEL_SECRET` | LINE Messaging API チャネルシークレット | LINE Developersコンソールから取得 |
| `GEMINI_API_KEY` | Google Gemini API キー | Google AI Studioから取得 |
| `NOTION_API_KEY` | Notion Integration Token | Notion Developersから取得 |

## GitHub Actions によるデプロイ手順

1. **GCPプロジェクトの設定**:
   - Google Cloud Projectを作成・選択します。
   - Cloud Functions API, Cloud Build API, Artifact Registry API を有効にします。
   - サービスアカウントを作成し、以下のロールを付与します。
     - `Cloud Functions Developer` (`roles/cloudfunctions.developer`)
     - `Service Account User` (`roles/iam.serviceAccountUser`)
     - `Cloud Run Admin` (`roles/run.admin`) ※Gen 2 で `--allow-unauthenticated` を使用するために必要
     - `Cloud Datastore User` (`roles/datastore.user`) ※会話履歴のFirestore保存に必要。GCPコンソールでは「Cloud Datastore ユーザー」と表示されます。
   - サービスアカウントのJSONキーをダウンロードし、GitHub Secretsの `GCP_SA_KEY` に登録します。

   > **注意**: 初めてFirestoreを使用する場合、GCPコンソールからデータベースを作成する必要があります。
   > 1. [Firestore コンソール](https://console.cloud.google.com/firestore) にアクセスします。
   > 2. 「データベースを作成」をクリックします。
   > 3. モードの選択で **「ネイティブ モード (Native mode)」** を選択します（推奨）。
   > 4. ロケーションは Cloud Functions と同じリージョン（例: `asia-northeast1`）を選択します。
   > 5. データベースIDは `(default)` のまま作成します。

2. **その他のSecrets登録**:
   - 上記の表に従い、LINE, Gemini, Notion のAPIキーをGitHub Secretsに登録します。

3. **デプロイの実行**:
   - `main` ブランチに `cloud_functions/` 配下の変更をプッシュすると、自動的にデプロイが開始されます。

## Cloud Build を使用する場合 (代替案)

もしGitHub Actionsを使用せず、Google Cloud Platform内で完結させたい場合は Cloud Build を使用できます。

1. `cloudbuild.yaml` を作成し、デプロイ手順を記述します。
2. Cloud Build トリガーを設定し、GitHubリポジトリへのプッシュを検知してビルドを実行するように設定します。
3. 環境変数は Cloud Build の設定画面または `_ENV_VARS` として管理する必要がありますが、秘匿情報の管理は Secret Manager との連携が必要になるなど、構成がやや複雑になります。

## 手動デプロイ (開発用)

ローカル環境から `gcloud` コマンドを使用して手動デプロイを行うことも可能です。

```bash
cd cloud_functions
gcloud functions deploy notigenie-backend \
  --gen2 \
  --runtime=python311 \
  --region=asia-northeast1 \
  --source=. \
  --entry-point=main \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars LINE_CHANNEL_ACCESS_TOKEN=your_token,LINE_CHANNEL_SECRET=your_secret,...
```
