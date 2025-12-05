from notion_client import Client
import os
import logging
import uuid

def test_fix():
    api_key = os.environ.get("NOTION_API_KEY")
    db_id = "1ff1ac9c8c708098bf4ac641178c9b8d"
    # Normalize
    db_id = str(uuid.UUID(db_id))

    print("Initializing client with notion_version='2022-06-28'")
    client = Client(auth=api_key, notion_version="2022-06-28")

    path = f"databases/{db_id}/query"
    try:
        results = client.request(path=path, method="POST", body={"page_size": 1})
        print("Success!")
        print(f"Results count: {len(results.get('results', []))}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_fix()
