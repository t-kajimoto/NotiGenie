
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

def verify_firestore_schemas():
    try:
        if not firebase_admin._apps:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        schema_collection_name = "notion_schemas"
        
        print(f"Checking documents in '{schema_collection_name}'...")
        docs = db.collection(schema_collection_name).stream()
        found_docs = []
        for doc in docs:
            found_docs.append(doc.id)
            print(f"- {doc.id}")
        
        if not found_docs:
            print("No documents found.")
        else:
            print(f"Total documents: {len(found_docs)}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    verify_firestore_schemas()
