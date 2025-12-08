# Firestoreへのスキーマ情報インポート手順

このディレクトリ内のスキーマ情報（JSONファイル）は、GitHub Actionsによってリポジトリへのプッシュ時に自動的にCloud Firestoreへインポートされます。

自動インポートを有効にするには、一度だけ以下の設定が必要です。

---

### GitHubリポジトリにSecretを設定する

Google Cloudから取得したサービスアカウントキー（JSON）の内容を、リポジトリのActions secretsに登録します。

1.  **リポジトリのSettingsに移動**
    -   このGitHubリポジトリの上部にある「Settings」タブをクリックします。

2.  **Secrets and variablesページに移動**
    -   左側のメニューから「Secrets and variables」>「Actions」を選択します。

3.  **新しいSecretを作成**
    -   「Repository secrets」のセクションにある「New repository secret」ボタンをクリックします。

4.  **`GCP_SA_KEY` を登録**
    -   **Name:** `GCP_SA_KEY`
    -   **Secret:** Google Cloudコンソールからダウンロードしたサービスアカウントキー（JSONファイル）の**内容全体**を貼り付けます。
    -   「Add secret」ボタンをクリックして保存します。

5.  **(オプション) `FIRESTORE_DATABASE` を登録**
    -   もしデフォルト (`(default)`) 以外のFirestoreデータベースを使用している場合は、同様に `FIRESTORE_DATABASE` という名前でデータベースIDをSecretに登録してください。

---

### 使い方

-   以上の設定が完了した後、この `firestore_import_data` ディレクトリ内のJSONファイルを変更（追加・修正・削除）してリポジトリにプッシュすると、自動的にGitHub Actionsが起動し、変更内容がFirestoreに反映されます。
-   アクションの実行結果は、リポジトリの「Actions」タブから確認できます。
