
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow importing modules from the project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Import adapters
from cloud_functions.core.interfaces.gateways.firestore_adapter import FirestoreAdapter
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter

def test_unified_db_access():
    print("--- 1. Testing Firestore Adapter ---")
    firestore_adapter = FirestoreAdapter()
    if not firestore_adapter.db:
        print("Error: Firestore client initialization failed.")
        return

    schemas = firestore_adapter.load_notion_schemas()
    if "master_db" not in schemas:
        print("Error: 'master_db' schema not found in Firestore.")
        print("Loaded schemas:", list(schemas.keys()))
        return
    else:
        print("Success: 'master_db' schema loaded.")
        print("Schema Title:", schemas["master_db"].get("title"))

    print("\n--- 2. Testing Notion Adapter (Create Page) ---")
    notion_adapter = NotionAdapter(schemas)
    if not notion_adapter.validate_connection():
        print("Error: Notion connection failed.")
        return

    # Create a test task
    test_title = "Unified DB Integration Test"
    test_props = {
        "Category": "Other",
        "Memo": "Created by verification script.",
        "DisplayDate": "Now"
    }
    
    create_result = notion_adapter.create_page(
        database_name="master_db",
        title=test_title,
        properties=test_props
    )
    
    if "error" in create_result:
        print(f"Error creating page: {create_result['error']}")
        return
    
    page_id = create_result.get("id")
    print(f"Success: Created page with ID: {page_id}")
    print(f"URL: {create_result.get('url')}")

    print("\n--- 3. Testing Notion Adapter (Search Page) ---")
    # Search for the created page
    search_result = notion_adapter.search_database(
        query=test_title,
        database_name="master_db"
    )
    
    found = False
    if isinstance(search_result, list):
        for item in search_result:
            if item.get("id").replace("-", "") == page_id.replace("-", ""):
                found = True
                print("Success: Found created page in search results.")
                print("Properties:", item.get("properties"))
                break
    
    if not found:
        print("Error: Created page not found in search results.")
        if isinstance(search_result, dict) and "error" in search_result:
            print(f"Search Error: {search_result['error']}")

if __name__ == "__main__":
    test_unified_db_access()
