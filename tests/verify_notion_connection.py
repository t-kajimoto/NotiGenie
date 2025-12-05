import os
import sys
import yaml
import logging
from notion_client import Client, APIResponseError

# Configure logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_connection():
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        logger.error("NOTION_API_KEY is not set in environment variables.")
        return False

    if api_key == "dummy":
        logger.warning("NOTION_API_KEY is set to 'dummy'. Real connection test will fail if attempted, but skipping for CI/Sandbox safety unless explicit.")
        # Proceed to test structure, but expect auth failure.

    try:
        # Load schemas
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(current_dir, "../cloud_functions/schemas.yaml")

        if not os.path.exists(schema_path):
             logger.error(f"schemas.yaml not found at {schema_path}")
             return False

        with open(schema_path, "r", encoding="utf-8") as f:
            schemas = yaml.safe_load(f)

        client = Client(auth=api_key, notion_version="2022-06-28")

        # 1. Test user/bot info (Authentication check)
        logger.info("Checking authentication (users.me)...")
        try:
            user = client.users.me()
            logger.info(f"Authenticated as: {user.get('name')} (Bot ID: {user.get('id')})")
        except APIResponseError as e:
            # Handle APIResponseError gracefully (no 'message' attribute in newer versions?)
            msg = str(e)
            logger.error(f"Authentication failed: {e.code} - {msg}")
            # If it's just dummy key, we stop here but don't crash script with traceback
            if api_key == "dummy":
                return False
            return False

        # 2. Test database access (Authorization check)
        menu_db = schemas.get("menu_list")
        if not menu_db:
            logger.error("'menu_list' not found in schemas.yaml")
            return False

        db_id = menu_db.get("id")
        # Normalize UUID
        import uuid
        try:
            db_id = str(uuid.UUID(db_id))
        except ValueError:
            pass # Keep as is if invalid

        logger.info(f"Checking access to 'menu_list' database (ID: {db_id})...")

        # Retrieve database metadata
        try:
            db_info = client.databases.retrieve(database_id=db_id)
            title_obj = db_info.get('title', [])
            title_text = title_obj[0].get('plain_text', 'No Title') if title_obj else 'No Title'
            logger.info(f"Successfully retrieved database metadata: {title_text}")
        except APIResponseError as e:
            logger.error(f"Failed to retrieve database metadata: {e.code} - {str(e)}")
            logger.error("Please ensure the integration is invited to the database.")
            return False

        # 3. Test query (Content access check)
        logger.info("Attempting a simple query (limit=1)...")
        try:
            # Check if query method exists (compatibility with notion-client 2.7.0)
            if hasattr(client.databases, "query"):
                results = client.databases.query(database_id=db_id, page_size=1)
            else:
                logger.info("client.databases.query method missing. Using client.request workaround.")
                results = client.request(
                    path=f"databases/{db_id}/query",
                    method="POST",
                    body={"page_size": 1}
                )

            count = len(results.get("results", []))
            logger.info(f"Query successful. Retrieved {count} items.")
        except APIResponseError as e:
             logger.error(f"Query failed: {e.code} - {str(e)}")
             return False

        return True

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if verify_connection():
        logger.info("✅ Notion connection verification PASSED.")
        sys.exit(0)
    else:
        logger.error("❌ Notion connection verification FAILED.")
        sys.exit(1)
