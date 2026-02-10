
import os
import sys

# Add the parent directory to sys.path to allow importing modules from the project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from notion_client import Client
from pprint import pprint

# Hardcoded ID for the new unified database
DATABASE_ID = "3031ac9c-8c70-8039-b008-e328acc6772d"

def inspect_database():
    notion_api_key = os.environ.get("NOTION_API_KEY")
    if not notion_api_key:
        print("Error: NOTION_API_KEY environment variable is not set.")
        return

    client = Client(auth=notion_api_key)

    try:
        response = client.databases.retrieve(database_id=DATABASE_ID)
        print(f"Database Name: {response.get('title', [{}])[0].get('plain_text', 'Untitled')}")
        print("Properties:")
        pprint(response.get("properties"))
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    inspect_database()
