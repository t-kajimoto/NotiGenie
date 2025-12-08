import json
import os
import tempfile
from google.cloud import firestore
import traceback
import sys

def setup_credentials():
    """
    環境変数 GCP_SA_KEY からサービスアカウント情報を読み込み、
    一時ファイルを作成して認証を設定します。
    """
    sa_key_json = os.environ.get("GCP_SA_KEY")
    if not sa_key_json:
        print("Error: GCP_SA_KEY environment variable is not set.", file=sys.stderr)
        print("Please set this variable with the content of your GCP service account JSON key.", file=sys.stderr)
        return False

    try:
        # 一時ファイルにサービスアカウントキーの内容を書き込む
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_cred_file:
            temp_cred_file.write(sa_key_json)
            # この一時ファイルのパスを環境変数に設定
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_cred_file.name

        print("Successfully created temporary credentials file from GCP_SA_KEY.")
        return True
    except Exception as e:
        print(f"Error setting up credentials from GCP_SA_KEY: {e}", file=sys.stderr)
        return False


def import_schemas_to_firestore():
    """
    'firestore_import_data' ディレクトリ内のJSONファイルを読み込み、
    Firestoreの 'notion_schemas' コレクションに書き込みます。
    """
    try:
        database_id = os.environ.get("FIRESTORE_DATABASE") or "(default)"
        db = firestore.Client(database=database_id)
        collection_ref = db.collection('notion_schemas')
        print(f"Successfully connected to Firestore database: {database_id}")

        import_dir = 'firestore_import_data'
        json_files = [f for f in os.listdir(import_dir) if f.endswith('.json')]

        if not json_files:
            print(f"No JSON files found in '{import_dir}'.")
            return

        print(f"Found {len(json_files)} files to import: {', '.join(json_files)}")

        for file_name in json_files:
            doc_id = os.path.splitext(file_name)[0]
            file_path = os.path.join(import_dir, file_name)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(data)
            print(f"Successfully imported '{file_name}' to document '{doc_id}'.")

        print("\nImport process completed successfully.")

    except Exception as e:
        print(f"An error occurred during the import process: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

if __name__ == '__main__':
    if setup_credentials():
        import_schemas_to_firestore()
    else:
        sys.exit(1)
