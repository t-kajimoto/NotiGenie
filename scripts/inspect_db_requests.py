
import os
import sys
import requests
from dotenv import load_dotenv
from pprint import pprint

# Add the parent directory to sys.path to allow importing modules from the project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Hardcoded ID for the new unified database
DATABASE_ID = "3031ac9c-8c70-8039-b008-e328acc6772d"

def inspect_database_requests():
    notion_api_key = os.environ.get("NOTION_API_KEY")
    if not notion_api_key:
        print("Error: NOTION_API_KEY environment variable is not set.")
        return

    print(f"Using Notion API Key: {notion_api_key[:4]}...{notion_api_key[-4:]}")
    
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Requesting: {url}")
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Database Title:", data.get("title", [{}])[0].get("plain_text", "Untitled"))
            print("Properties:")
            pprint(data.get("properties"))
        else:
            print("Error Response:")
            pprint(response.json())
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    inspect_database_requests()
