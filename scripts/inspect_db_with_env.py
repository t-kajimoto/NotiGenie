
import os
import sys
from dotenv import load_dotenv
from pprint import pprint
from notion_client import Client

# Add the parent directory to sys.path to allow importing modules from the project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Hardcoded ID for the new unified database
DATABASE_ID = "3031ac9c-8c70-8039-b008-e328acc6772d"

def inspect_database():
    notion_api_key = os.environ.get("NOTION_API_KEY")
    if not notion_api_key:
        print("Error: NOTION_API_KEY environment variable is not set.")
        return

    client = Client(auth=notion_api_key)

    print("Available methods on client.databases:", dir(client.databases))

    try:
        # Try search to find the database
        print("Searching for database...")
        response = client.search(query='タスク・買い物・献立管理', filter={'property': 'object', 'value': 'database'})
        results = response.get("results", [])
        if results:
            print("Found database via search:")
            db = results[0]
            pprint(db.get("properties"))
        else:
            print("Database not found via search.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    inspect_database()
