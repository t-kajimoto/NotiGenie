
import os
import sys
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow importing modules from the project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def update_firestore_schema():
    # Initialize Firebase Admin SDK
    # Assuming explicit credentials are not needed if running in environment with GOOGLE_APPLICATION_CREDENTIALS
    # or if we can pick up default credentials.
    # However, for local execution, we might need to rely on 'gcloud auth application-default login' having been run.
    
    database_id = os.environ.get("FIRESTORE_DATABASE") or "(default)"
    print(f"Connecting to Firestore database: {database_id}")

    try:
        if not firebase_admin._apps:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        
        # database argument might not be supported in this version of firebase-admin
        # If using a specific database, it should be configured in the App options or Project settings
        db = firestore.client()
        schema_collection_name = "notion_schemas" # Defined in config.py
        
        # 1. Delete existing documents
        print(f"Deleting existing documents in '{schema_collection_name}'...")
        docs = db.collection(schema_collection_name).stream()
        deleted = 0
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        print(f"Deleted {deleted} documents.")

        # 2. Add new master_db schema
        print("Adding new master_db schema...")
        
        new_schema = {
            "id": "3031ac9c-8c70-8039-b008-e328acc6772d",
            "title": "タスク・買い物・献立管理",
            "description": "統合データベース。買い物、ToDo、献立を一元管理します。'カテゴリ' プロパティで分類します。",
            "properties": {
                "タイトル": {
                    "type": "title",
                    "description": "タスクやアイテムの名前"
                },
                "カテゴリ": {
                    "type": "select",
                    "options": ["Shopping", "ToDo", "Menu", "Other"],
                    "description": "データの種類 (Shopping/ToDo/Menu/Other)"
                },
                "メモ": {
                    "type": "rich_text",
                    "description": "詳細情報、補足、URLなど"
                },
                "予定日": {
                    "type": "date",
                    "description": "明確な日付（ソート・カレンダー用）"
                },
                "予定日表示": {
                    "type": "rich_text",
                    "description": "自然言語での時期（例: '来週', 'なる早'）"
                },
                "完了日": {
                    "type": "date",
                    "description": "完了した日付。未完了なら空。"
                }
            }
        }
        
        db.collection(schema_collection_name).document("master_db").set(new_schema)
        print("Successfully added 'master_db' schema.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    update_firestore_schema()
