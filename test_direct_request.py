import os
import requests
import uuid

def test_request():
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        print("No API Key")
        return

    db_id = "1ff1ac9c8c708098bf4ac641178c9b8d"
    # Normalize
    db_id = str(uuid.UUID(db_id))

    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json"
    }
    data = {"page_size": 1}

    print(f"Requesting {url}...")
    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test_request()
